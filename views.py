"""
REST API Views for the Marine Algae Biofuel Prediction System.
"""
import json
import os
from django.conf import settings
from django.db.models import Count, Avg, Max, Min, Q
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import AlgaeSpecies, CoastalRegion, SpeciesStateOccurrence, PredictionResult
from .serializers import (
    AlgaeSpeciesListSerializer,
    AlgaeSpeciesDetailSerializer,
    CoastalRegionSerializer,
    CoastalRegionDetailSerializer,
    SpeciesStateOccurrenceSerializer,
    PredictionResultSerializer,
    PredictionInputSerializer,
)


class NoPagination(PageNumberPagination):
    page_size = None


class SpeciesPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AlgaeSpeciesViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for species data."""
    queryset = AlgaeSpecies.objects.all()
    pagination_class = SpeciesPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AlgaeSpeciesDetailSerializer
        return AlgaeSpeciesListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by phylum
        phylum = self.request.query_params.get('phylum')
        if phylum:
            qs = qs.filter(phylum__icontains=phylum)
        # Filter by name search
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(genus__icontains=search))
        # Filter by state
        state = self.request.query_params.get('state')
        if state:
            qs = qs.filter(state_occurrences__state__state_name__icontains=state)
        return qs.distinct()

    @action(detail=True, methods=['get'])
    def states(self, request, pk=None):
        """Get all state occurrences for a species."""
        species = self.get_object()
        occurrences = species.state_occurrences.all()
        serializer = SpeciesStateOccurrenceSerializer(occurrences, many=True)
        return Response(serializer.data)


class CoastalRegionViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for coastal regions."""
    queryset = CoastalRegion.objects.all()
    serializer_class = CoastalRegionSerializer
    pagination_class = NoPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CoastalRegionDetailSerializer
        return CoastalRegionSerializer

    @action(detail=True, methods=['get'])
    def species(self, request, pk=None):
        """Get all species found in a specific state."""
        region = self.get_object()
        occurrences = region.species_occurrences.select_related('species').order_by('-biofuel_yield_L_per_ha')
        serializer = SpeciesStateOccurrenceSerializer(occurrences, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def compare(self, request):
        """Compare environmental parameters across states."""
        states = CoastalRegion.objects.annotate(
            species_count=Count('species_occurrences'),
            avg_yield=Avg('species_occurrences__biofuel_yield_L_per_ha'),
            max_yield=Max('species_occurrences__biofuel_yield_L_per_ha'),
        )
        data = []
        for s in states:
            data.append({
                'id': s.id,
                'state_name': s.state_name,
                'state_code': s.state_code,
                'avg_sea_temperature': s.avg_sea_temperature,
                'avg_salinity': s.avg_salinity,
                'avg_ph': s.avg_ph,
                'avg_light_intensity': s.avg_light_intensity,
                'species_count': s.species_count,
                'avg_yield': round(s.avg_yield, 2) if s.avg_yield else 0,
                'max_yield': round(s.max_yield, 2) if s.max_yield else 0,
            })
        return Response(data)


@api_view(['POST'])
def predict_yield(request):
    """Run prediction using all 3 ML models."""
    serializer = PredictionInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    input_data = serializer.validated_data

    try:
        from ml_engine.predict import predict
        result = predict(input_data)
    except Exception as e:
        return Response(
            {'error': f'Prediction failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Save prediction
    prediction = PredictionResult.objects.create(
        rf_yield=result['rf_yield'],
        gb_yield=result['gb_yield'],
        nn_yield=result['nn_yield'],
        ensemble_yield=result['ensemble_yield'],
        best_model=result['best_model'],
        confidence_score=result['confidence_score'],
        input_parameters=input_data,
    )

    result['prediction_id'] = prediction.pk
    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
def prediction_history(request):
    """Get past prediction results."""
    predictions = PredictionResult.objects.all()[:50]
    serializer = PredictionResultSerializer(predictions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def dashboard_stats(request):
    """Dashboard KPIs and summary statistics."""
    total_species = AlgaeSpecies.objects.count()
    total_states = CoastalRegion.objects.count()
    total_occurrences = SpeciesStateOccurrence.objects.count()

    yield_stats = SpeciesStateOccurrence.objects.aggregate(
        avg_yield=Avg('biofuel_yield_L_per_ha'),
        max_yield=Max('biofuel_yield_L_per_ha'),
        min_yield=Min('biofuel_yield_L_per_ha'),
    )

    # Phylum distribution
    phylum_dist = AlgaeSpecies.objects.values('phylum').annotate(
        count=Count('id')
    ).order_by('-count')

    # Top 10 species by yield
    top_species = SpeciesStateOccurrence.objects.select_related(
        'species', 'state'
    ).order_by('-biofuel_yield_L_per_ha')[:10]

    top_species_data = [
        {
            'name': occ.species.name,
            'phylum': occ.species.phylum,
            'state': occ.state.state_name,
            'yield': occ.biofuel_yield_L_per_ha,
            'lipid_content': occ.species.lipid_content,
        }
        for occ in top_species
    ]

    # Species per state
    state_species_count = CoastalRegion.objects.annotate(
        species_count=Count('species_occurrences'),
        avg_yield=Avg('species_occurrences__biofuel_yield_L_per_ha'),
    ).values('state_name', 'state_code', 'species_count', 'avg_yield', 'latitude', 'longitude')

    # Phylum per state heatmap data
    heatmap_data = []
    for region in CoastalRegion.objects.all():
        phylum_counts = region.species_occurrences.values(
            'species__phylum'
        ).annotate(count=Count('id'))
        for pc in phylum_counts:
            heatmap_data.append({
                'state': region.state_name,
                'phylum': pc['species__phylum'],
                'count': pc['count'],
            })

    # Best state for biofuel
    best_state = CoastalRegion.objects.annotate(
        avg_yield=Avg('species_occurrences__biofuel_yield_L_per_ha')
    ).order_by('-avg_yield').first()

    return Response({
        'total_species': total_species,
        'total_states': total_states,
        'total_occurrences': total_occurrences,
        'avg_yield': round(yield_stats['avg_yield'], 2) if yield_stats['avg_yield'] else 0,
        'max_yield': round(yield_stats['max_yield'], 2) if yield_stats['max_yield'] else 0,
        'min_yield': round(yield_stats['min_yield'], 2) if yield_stats['min_yield'] else 0,
        'phylum_distribution': list(phylum_dist),
        'top_species': top_species_data,
        'state_species_count': list(state_species_count),
        'heatmap_data': heatmap_data,
        'best_state': best_state.state_name if best_state else 'N/A',
        'total_predictions': PredictionResult.objects.count(),
    })


@api_view(['GET'])
def model_comparison(request):
    """Get ML model metrics and feature importance."""
    metrics_path = os.path.join(settings.ML_MODELS_DIR, 'metrics.json')
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
    else:
        metrics = {
            'random_forest': {'r2': 0, 'rmse': 0, 'mae': 0},
            'gradient_boosting': {'r2': 0, 'rmse': 0, 'mae': 0},
            'neural_network': {'r2': 0, 'rmse': 0, 'mae': 0},
            'feature_importance': {},
            'actual_vs_predicted': {},
        }

    return Response(metrics)


@api_view(['GET'])
def top_species(request):
    """Get top N species, optionally filtered by state."""
    n = int(request.query_params.get('n', 10))
    state = request.query_params.get('state')

    qs = SpeciesStateOccurrence.objects.select_related('species', 'state')
    if state:
        qs = qs.filter(state__state_name__icontains=state)

    top = qs.order_by('-biofuel_yield_L_per_ha')[:n]
    data = [
        {
            'name': occ.species.name,
            'phylum': occ.species.phylum,
            'state': occ.state.state_name,
            'yield': occ.biofuel_yield_L_per_ha,
            'lipid_content': occ.species.lipid_content,
            'growth_rate': occ.species.growth_rate,
        }
        for occ in top
    ]
    return Response(data)


@api_view(['GET'])
def state_environmental_params(request):
    """Get environmental parameters for a specific state (used to auto-fill prediction form)."""
    state_name = request.query_params.get('state')
    if not state_name:
        return Response({'error': 'state parameter required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        region = CoastalRegion.objects.get(state_name__icontains=state_name)
    except CoastalRegion.DoesNotExist:
        return Response({'error': 'State not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get average environmental params from occurrences
    env = region.species_occurrences.aggregate(
        avg_temp_min=Avg('temp_min'),
        avg_temp_max=Avg('temp_max'),
        avg_salinity=Avg('salinity'),
        avg_ph_min=Avg('ph_min'),
        avg_ph_max=Avg('ph_max'),
        avg_light=Avg('light_intensity'),
    )

    return Response({
        'state_name': region.state_name,
        'temp_min': round(env['avg_temp_min'] or 0, 1),
        'temp_max': round(env['avg_temp_max'] or 0, 1),
        'salinity': round(env['avg_salinity'] or 0, 1),
        'ph_min': round(env['avg_ph_min'] or 0, 1),
        'ph_max': round(env['avg_ph_max'] or 0, 1),
        'light_intensity': round(env['avg_light'] or 0, 1),
    })

import google.generativeai as genai

@api_view(['POST'])
def identify_species(request):
    import base64
    from io import BytesIO
    from PIL import Image
    if 'image' not in request.FILES:
        return Response({'error': 'No image provided'}, status=400)
    
    image_file = request.FILES['image']
    try:
        img = Image.open(image_file)
        
        # Setup Gemini
        gemini_api_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_api_key:
            from django.conf import settings
            env_path = os.path.join(settings.BASE_DIR, '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('GEMINI_API_KEY='):
                            gemini_api_key = line.split('=', 1)[1].strip()
                            break
            
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        prompt = """You are an expert marine biologist. Identify the marine algae species from this image.
Respond ONLY with a valid JSON document in this exact structure:
{
  "species_name": "Scientific Name of algae",
  "common_name": "Common Name if any",
  "phylum": "Phylum name",
  "class": "Class Name",
  "description": "Short description of the algae",
  "confidence": 95,
  "features": ["feature 1", "feature 2"],
  "habitat": "Typical habitat",
  "biochemical": {
     "lipid_content": 15.5,
     "carbohydrate_content": 25.0,
     "protein_content": 18.0,
     "moisture_content": 10.0,
     "ash_content": 5.0,
     "growth_rate_g_L_day": 0.45,
     "co2_absorption_g_g": 1.25,
     "estimated_biofuel_yield_L_ha": 6500.0
  }
}
Provide scientific estimates based on your knowledge if exact data for this specific species is rare."""
        response = model.generate_content([prompt, img])
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        
        # DB lookup - Try exact match, then fuzzy icontains, then genus-only
        sps_name = data['species_name'].strip()
        sps = AlgaeSpecies.objects.filter(name__iexact=sps_name).first()
        if not sps:
            sps = AlgaeSpecies.objects.filter(name__icontains=sps_name).first()
        if not sps and ' ' in sps_name:
            genus = sps_name.split(' ')[0]
            sps = AlgaeSpecies.objects.filter(name__startswith=genus).first()
            
        is_new = False
        if not sps:
            # AUTOMATIC ADDITION FEATURE
            is_new = True
            import uuid
            bc = data.get('biochemical', {})
            sps = AlgaeSpecies.objects.create(
                species_id=f"AI-{uuid.uuid4().hex[:8].upper()}",
                name=sps_name,
                genus=sps_name.split(' ')[0] if ' ' in sps_name else '',
                phylum=data.get('phylum', 'Unknown'),
                lipid_content=bc.get('lipid_content', 0),
                carbohydrate_content=bc.get('carbohydrate_content', 0),
                protein_content=bc.get('protein_content', 0),
                moisture_content=bc.get('moisture_content', 0),
                ash_content=bc.get('ash_content', 0),
                growth_rate=bc.get('growth_rate_g_L_day', 0),
                co2_absorption=bc.get('co2_absorption_g_g', 0)
            )
            # Add a default coastal occurrence (e.g. in a diverse state like Tamil Nadu)
            from .models import CoastalRegion, SpeciesStateOccurrence
            tn = CoastalRegion.objects.filter(state_name__icontains='Tamil').first()
            if tn:
                SpeciesStateOccurrence.objects.create(
                    species=sps,
                    state=tn,
                    temp_min=24, temp_max=32, salinity=34, ph_min=7.8, ph_max=8.2,
                    light_intensity=450,
                    biofuel_yield_L_per_ha=bc.get('estimated_biofuel_yield_L_ha', 5000)
                )




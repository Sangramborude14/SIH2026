export interface LocationMapItem {
  id: string;
  name: string;
  district: string;
  state: string;
  latitude: number;
  longitude: number;
  elevation: number;
  slope_angle: number;
  susceptibility_score: number;
  risk_level: string;
  risk_score: number;
  confidence_score: number;
  active_event: boolean;
  event_id?: string | null;
  event_status?: string | null;
  event_severity?: string | null;
  rainfall_24h?: number;
  rainfall_1h?: number;
  soil_moisture?: number;
  trend_direction: string;
  trajectory?: string;
  primary_factor?: string;
  last_updated: string;
  anomaly_score?: number | null;
  anomaly_level?: string | null;
  forecast_probabilities?: Record<string, number>;
  forecast_available?: boolean;
  model_version?: string | null;
  model_status?: string | null;
  data_freshness?: string;
}



export interface FactorDetail {
  name: string;
  raw_value: any;
  normalized_score: number; // 0.0 to 1.0
  weight: number;           // 0.0 to 1.0
  contribution: number;     // Points out of 100
  status: string;           // 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
  impact_type?: string;     // 'INCREASE_RISK', 'DECREASE_RISK', 'NEUTRAL'
  description?: string | null;
}

export interface AnomalyReport {
  metric: string;
  value: number;
  baseline: number;
  anomaly_score: number;
  is_anomalous: boolean;
  description?: string | null;
}

export interface TrendReport {
  metric: string;
  direction: string;
  slope: number;
  description?: string | null;
}

export interface DisasterEventItem {
  id: string;
  event_type: string;
  location_id: string;
  status: string;
  severity: string;
  risk_score: number;
  initial_risk: number;
  peak_risk: number;
  peak_severity: string;
  confidence_score: number;
  trajectory: string;
  detected_at: string;
  updated_at: string;
  expected_start?: string | null;
  expected_peak?: string | null;
  affected_area?: string | null;
  summary: string;
}

export interface WeatherObservationItem {
  id: string;
  location_id: string;
  timestamp: string;
  temperature?: number | null;
  humidity?: number | null;
  pressure?: number | null;
  wind_speed?: number | null;
  wind_direction?: number | null;
  rainfall_1h?: number | null;
  rainfall_6h?: number | null;
  rainfall_24h?: number | null;
  soil_moisture?: number | null;
  source: string;
  source_version?: string;
  freshness_status?: string;
  retrieved_at?: string;
  created_at: string;
}

export interface RiskAssessmentItem {
  id: string;
  location_id: string;
  timestamp: string;
  hazard_type: string;
  risk_level: string;
  risk_score: number;
  confidence_score: number;
  trajectory: string;
  reason: string;
  reason_codes: string[];
  factors: FactorDetail[];
  data_quality?: {
    status: string;
    completeness_score: number;
    freshness_score: number;
    missing_fields: string[];
    invalid_fields: string[];
    quality_notes?: string;
  } | null;
  signal_agreement?: {
    agreement_score: number;
    coherent_signals_count: number;
    conflicting_signals_count: number;
    agreement_level: string;
    details: string;
  } | null;
  assessment_version: string;
  created_at: string;
}

export interface EventTimelineMilestoneItem {
  timestamp: string;
  time_label: string;
  title: string;
  description: string;
  category: string;
  severity?: string | null;
}

export interface ProviderHealthItem {
  name: string;
  status: string;
  source_type: string;
  last_success?: string | null;
  last_failure?: string | null;
  consecutive_failures: number;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  last_latency_ms?: number | null;
  error_message?: string | null;
}

export interface DashboardSummaryData {
  active_events_count: number;
  critical_events_count: number;
  high_risk_count: number;
  moderate_risk_count: number;
  low_risk_count: number;
  total_monitored_locations: number;
  highest_risk_score: number;
  highest_risk_level: string;
  last_engine_run: string;
  data_sources_status: string;
  data_mode?: string;
}

export interface LocationInvestigationData {
  location: {
    id: string;
    name: string;
    latitude: number;
    longitude: number;
    district: string;
    state: string;
    elevation: number;
    slope_angle: number;
    susceptibility_score: number;
    created_at: string;
  };
  latest_assessment: RiskAssessmentItem | null;
  active_event: DisasterEventItem | null;
  weather_history: WeatherObservationItem[];
  risk_history: RiskAssessmentItem[];
  event_timeline: EventTimelineMilestoneItem[];
}

export interface ShortDurationItem {
  period: string;
  hours: number;
  rainfall_mm: number | null;
  has_data: boolean;
  status_label: string;
}

export interface IDCurvePoint {
  duration_hours: number;
  threshold_rainfall_mm: number;
  critical_intensity_mm_h: number;
}

export interface SoilDepthLayer {
  depth_range: string;
  depth_label: string;
  moisture_pct: number;
  volumetric_m3_m3: number;
  relative_wetness: string;
  bar_fill_pct: number;
}

export interface ShortDurationAccumulation {
  hours: number;
  label: string;
  rainfall_mm: number;
  intensity_mm_h: number;
  is_peak_window: boolean;
}

export interface TimelineSeriesItem {
  timestamp: string;
  timestamp_str: string;
  is_observed: boolean;
  rainfall_rate_mm_h: number;
  rainfall_24h_mm: number;
  soil_moisture_pct: number;
  risk_score: number;
  confidence_score: number;
  event_marker?: string | null;
}

export interface AssessmentDriver {
  factor_name: string;
  level: string;
  contribution_points: number;
  measured_value_str: string;
  driver_type: string;
}

export interface DataProvenance {
  signal_name: string;
  source_provider: string;
  observation_time: string;
  retrieval_time: string;
  freshness_status: string;
  data_category: string;
}

export interface TriggerFactor {
  name: string;
  value: string;
  severity: string;
  type: string;
  description: string;
}

export interface ConditioningFactor {
  name: string;
  value: string;
  severity: string;
  type: string;
  description: string;
}

export interface DataQualityMatrixItem {
  parameter: string;
  status: string;
  data_source: string;
  last_updated: string;
  note?: string | null;
}

export interface UncertaintyData {
  assessment_confidence_pct: number;
  data_completeness_pct: number;
  data_freshness_pct: number;
  signal_agreement_pct: number;
  summary: string;
  known_missing_inputs: string[];
}

export interface EarthObservationSummaryItem {
  provider: string;
  status: string;
  configured: boolean;
  latest_acquisition_time?: string | null;
  collection?: string;
  spatial_coverage?: string;
  product_status?: string;
  note?: string;
}

export interface ScientificInvestigationData {
  station: {
    id: string;
    name: string;
    district: string;
    state: string;
    latitude: number;
    longitude: number;
    elevation_m?: number;
    slope_angle_deg?: number;
    susceptibility_score?: number;
  };
  current_assessment: {
    risk_score: number;
    risk_level: string;
    confidence_score: number;
    confidence_pct?: number;
    timestamp: string;
    active_event?: boolean;
    event_id?: string | null;
    event_severity?: string | null;
    event_status?: string | null;
    summary_text?: string;
    disclaimer?: string;
  };
  risk_trajectory: {
    current_risk_score: number;
    current_risk_level: string;
    score_6h_ago: number;
    level_6h_ago: string;
    delta_6h: number;
    direction: string;
    rate_of_change_points_per_hour: number;
    acceleration_label?: string;
    explanation: string;
  };
  rainfall: {
    intensity: {
      current_intensity_mm_h: number;
      rolling_3h_mm: number;
      rolling_6h_mm: number;
      rolling_24h_mm: number;
      classification: string;
      source_note: string;
    };
    max_short_duration?: {
      max_1h_mm: number;
      max_1h_timestamp?: string | null;
      max_3h_mm: number;
      max_6h_mm: number;
      window_hours: number;
    };
    event_segmentation?: {
      event_active: boolean;
      event_start_time?: string | null;
      event_peak_time?: string | null;
      peak_intensity_mm_h: number;
      event_duration_hours: number;
      total_event_rainfall_mm: number;
      classification: string;
    };
    short_duration_table: ShortDurationAccumulation[];
    persistence: {
      current_wet_spell_hours: number;
      consecutive_dry_hours: number;
      persistence_level: string;
      explanation: string;
    };
    antecedent_wetness_index: {
      api_value: number;
      decay_factor_k: number;
      days_analyzed: number;
      classification: string;
      historical_percentile: number;
      formula_reference: string;
      explanation: string;
    };
    anomaly: {
      anomaly_score_sigma: number;
      departure_mm: number;
      is_anomalous: boolean;
      baseline_source: string;
      explanation: string;
    };
    intensity_duration: {
      active_duration_hours: number;
      cumulative_rainfall_mm: number;
      average_intensity_mm_h: number;
      max_hourly_intensity_mm_h: number;
      prototype_threshold_rainfall_mm: number;
      is_above_prototype_threshold: boolean;
      threshold_margin_mm: number;
      reference_curve: IDCurvePoint[];
      status_text: string;
      disclaimer: string;
    };
  };
  soil_moisture: {
    current_composite_pct: number;
    vertical_profile: SoilDepthLayer[];
    trend: {
      delta_1h_pct: number;
      delta_3h_pct: number;
      delta_6h_pct: number;
      delta_24h_pct: number;
      direction: string;
      trend_rate_pct_per_hour: number;
      explanation: string;
    };
    percentile: {
      current_moisture_pct: number;
      historical_percentile: number;
      status_label: string;
      reference_source: string;
      explanation: string;
    };
    rainfall_response?: {
      response_detected: boolean;
      lag_time_hours: number;
      correlation_label: string;
    };
    measurement_type: string;
    disclaimer: string;
  };
  hydrometeorological_state: {
    rainfall_intensity_level: string;
    rainfall_persistence_level: string;
    accumulation_24h_level: string;
    antecedent_wetness_level: string;
    soil_moisture_level: string;
    moisture_trend_level: string;
    elevated_signals_count: number;
    total_signals_count: number;
    signal_agreement_label: string;
    synthesis_summary: string;
  };
  terrain: {
    elevation_m: number;
    slope_angle_deg: number;
    slope_classification: string;
    aspect_label?: string;
    terrain_susceptibility_score: number;
    historical_susceptibility_rating: string;
    historical_incident_count?: number;
    terrain_source: string;
    data_resolution?: string;
    data_freshness?: string;
    is_simulated_terrain?: boolean;
    geotechnical_notes: string;
  };
  triggers?: TriggerFactor[];
  conditioning_factors?: ConditioningFactor[];
  uncertainty?: UncertaintyData;
  data_quality_matrix?: DataQualityMatrixItem[];
  earth_observation?: EarthObservationSummaryItem;
  timeline_series: TimelineSeriesItem[];
  forecast: {
    expected_rainfall_24h_mm: number;
    expected_wet_hours_24h: number;
    expected_max_hourly_mm: number;
    expected_moisture_trend: string;
    projected_risk_trajectory: string;
    forecast_period_label: string;
    provenance_note: string;
  };
  assessment_drivers: AssessmentDriver[];
  evidence_summary: {
    supporting_elevated_risk: string[];
    limiting_uncertain_factors: string[];
    missing_sensor_observations: string[];
  };
  field_reports?: any[];
  provenance: DataProvenance[];
  generated_at: string;
  engine_version?: string;
  data_mode: string;
}



"""add_landslide_events_and_telemetry_tables

Revision ID: 4c99881ae011
Revises: 3b88770fd923
Create Date: 2026-09-03 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c99881ae011'
down_revision: Union[str, None] = '3b88770fd923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create landslide_events table
    op.create_table(
        'landslide_events',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('external_id', sa.String(length=128), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False),
        sa.Column('district', sa.String(length=64), nullable=False),
        sa.Column('location_name', sa.String(length=256), nullable=True),
        sa.Column('occurrence_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('occurrence_date', sa.Date(), nullable=False),
        sa.Column('time_precision', sa.String(length=32), nullable=False, server_default='DATE_ONLY'),
        sa.Column('landslide_type', sa.String(length=64), nullable=False, server_default='RAINFALL_TRIGGERED_SLIDE'),
        sa.Column('trigger', sa.String(length=128), nullable=True, server_default='HEAVY_RAINFALL'),
        sa.Column('verification_status', sa.String(length=64), nullable=False, server_default='FIELD_VALIDATED'),
        sa.Column('source_confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('original_source', sa.String(length=256), nullable=True),
        sa.Column('source_metadata', sa.JSON(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dataset_version', sa.String(length=32), nullable=False, server_default='v1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_landslide_events_source', 'landslide_events', ['source'])
    op.create_index('ix_landslide_events_external_id', 'landslide_events', ['external_id'])
    op.create_index('ix_landslide_events_lat', 'landslide_events', ['latitude'])
    op.create_index('ix_landslide_events_lon', 'landslide_events', ['longitude'])
    op.create_index('ix_landslide_events_state', 'landslide_events', ['state'])
    op.create_index('ix_landslide_events_district', 'landslide_events', ['district'])
    op.create_index('ix_landslide_events_occ_date', 'landslide_events', ['occurrence_date'])
    op.create_index('idx_landslide_source_ext', 'landslide_events', ['source', 'external_id'])
    op.create_index('idx_landslide_geo_date', 'landslide_events', ['latitude', 'longitude', 'occurrence_date'])
    op.create_index('idx_landslide_state_district', 'landslide_events', ['state', 'district'])

    # 2. Create weather_forecast_snapshots table
    op.create_table(
        'weather_forecast_snapshots',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('location_id', sa.String(length=64), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('forecast_issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('forecast_valid_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('forecast_horizon_hours', sa.Integer(), nullable=False),
        sa.Column('precipitation_mm', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('rain_mm', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('soil_moisture', sa.Float(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Float(), nullable=True),
        sa.Column('wind_speed', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=False, server_default='OPEN_METEO'),
        sa.Column('model_name', sa.String(length=64), nullable=False, server_default='open-meteo-seamless'),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_forecast_snap_loc_valid', 'weather_forecast_snapshots', ['location_id', 'forecast_valid_at'])
    op.create_index('idx_forecast_snap_loc_issued', 'weather_forecast_snapshots', ['location_id', 'forecast_issued_at'])
    op.create_index('idx_forecast_snap_horizon', 'weather_forecast_snapshots', ['location_id', 'forecast_horizon_hours', 'forecast_valid_at'])

    # 3. Create ml_model_versions table
    op.create_table(
        'ml_model_versions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('model_name', sa.String(length=128), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('forecast_horizon_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('training_source', sa.String(length=32), nullable=False, server_default='SYNTHETIC'),
        sa.Column('dataset_name', sa.String(length=128), nullable=False, server_default='synthetic_landslide_v1'),
        sa.Column('dataset_version', sa.String(length=32), nullable=False, server_default='v1.0'),
        sa.Column('artifact_path', sa.String(length=512), nullable=False),
        sa.Column('artifact_sha256', sa.String(length=64), nullable=True),
        sa.Column('feature_schema_version', sa.String(length=32), nullable=False, server_default='2.0.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='READY'),
        sa.Column('metrics_json', sa.JSON(), nullable=True),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_ml_model_ver_name_status', 'ml_model_versions', ['model_name', 'status'])
    op.create_index('idx_ml_model_ver_horizon', 'ml_model_versions', ['forecast_horizon_hours', 'status'])

    # 4. Add unique constraint to weather_observations
    try:
        op.create_unique_constraint(
            'uq_weather_loc_time_source_type',
            'weather_observations',
            ['location_id', 'timestamp', 'source', 'observation_type']
        )
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_constraint('uq_weather_loc_time_source_type', 'weather_observations', type_='unique')
    except Exception:
        pass
    op.drop_table('ml_model_versions')
    op.drop_table('weather_forecast_snapshots')
    op.drop_table('landslide_events')

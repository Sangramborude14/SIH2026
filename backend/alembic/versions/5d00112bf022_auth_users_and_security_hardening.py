"""auth_users_and_security_hardening

Revision ID: 5d00112bf022
Revises: 4c99881ae011
Create Date: 2026-09-05 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d00112bf022'
down_revision: Union[str, None] = '4c99881ae011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=128), nullable=False),
        sa.Column('phone_number', sa.String(length=32), nullable=True),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='CITIZEN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=False)
    op.create_index('idx_users_role_active', 'users', ['role', 'is_active'], unique=False)

    # 2. Refresh Tokens Table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'], unique=False)
    op.create_index('idx_refresh_tokens_user_expires', 'refresh_tokens', ['user_id', 'expires_at'], unique=False)
    op.create_index('idx_refresh_tokens_hash_revoked', 'refresh_tokens', ['token_hash', 'revoked_at'], unique=False)

    # 3. Citizen SOS columns and indexes
    try:
        op.add_column('citizen_sos', sa.Column('user_id', sa.String(length=64), nullable=True))
        op.add_column('citizen_sos', sa.Column('tracking_token', sa.String(length=64), nullable=True))
        op.create_index(op.f('ix_citizen_sos_user_id'), 'citizen_sos', ['user_id'], unique=False)
        op.create_index(op.f('ix_citizen_sos_tracking_token'), 'citizen_sos', ['tracking_token'], unique=False)
        op.create_index('idx_citizen_sos_user_created', 'citizen_sos', ['user_id', 'created_at'], unique=False)
    except Exception:
        pass

    # 4. Citizen Reports columns and indexes
    try:
        op.add_column('citizen_reports', sa.Column('user_id', sa.String(length=64), nullable=True))
        op.add_column('citizen_reports', sa.Column('thumbnail_storage_key', sa.String(length=255), nullable=True))
        op.add_column('citizen_reports', sa.Column('photo_content_hash', sa.String(length=64), nullable=True))
        op.create_index(op.f('ix_citizen_reports_user_id'), 'citizen_reports', ['user_id'], unique=False)
        op.create_index(op.f('ix_citizen_reports_photo_content_hash'), 'citizen_reports', ['photo_content_hash'], unique=False)
        op.create_index('idx_citizen_rep_user_created', 'citizen_reports', ['user_id', 'created_at'], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index('idx_citizen_rep_user_created', table_name='citizen_reports')
        op.drop_index(op.f('ix_citizen_reports_photo_content_hash'), table_name='citizen_reports')
        op.drop_index(op.f('ix_citizen_reports_user_id'), table_name='citizen_reports')
        op.drop_column('citizen_reports', 'photo_content_hash')
        op.drop_column('citizen_reports', 'thumbnail_storage_key')
        op.drop_column('citizen_reports', 'user_id')
    except Exception:
        pass

    try:
        op.drop_index('idx_citizen_sos_user_created', table_name='citizen_sos')
        op.drop_index(op.f('ix_citizen_sos_tracking_token'), table_name='citizen_sos')
        op.drop_index(op.f('ix_citizen_sos_user_id'), table_name='citizen_sos')
        op.drop_column('citizen_sos', 'tracking_token')
        op.drop_column('citizen_sos', 'user_id')
    except Exception:
        pass

    op.drop_table('refresh_tokens')
    op.drop_table('users')

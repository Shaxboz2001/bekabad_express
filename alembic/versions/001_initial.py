"""initial

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('full_name', sa.String(150), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('admin','driver','passenger', name='userrole'), nullable=False, server_default='passenger'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
    )
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'], unique=True)
    op.create_index('ix_users_phone', 'users', ['phone'], unique=True)

    op.create_table('driver_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('car_model', sa.String(100), nullable=False),
        sa.Column('car_number', sa.String(20), nullable=False),
        sa.Column('car_color', sa.String(50), nullable=True),
        sa.Column('car_type', sa.Enum('any','sedan','minivan','cargo_van', name='cartype'), nullable=False, server_default='sedan'),
        sa.Column('car_year', sa.Integer(), nullable=True),
        sa.Column('license_number', sa.String(50), nullable=False),
        sa.Column('seats_available', sa.Integer(), server_default='4'),
        sa.Column('is_available', sa.Boolean(), server_default='true'),
        sa.Column('rating', sa.Float(), server_default='5.0'),
        sa.Column('total_trips', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    op.create_table('pricing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.Enum('bekobod_to_tashkent','tashkent_to_bekobod', name='tripdirection'), nullable=False),
        sa.Column('category', sa.Enum('passenger','passenger_small_cargo','cargo', name='tripcategory'), nullable=False),
        sa.Column('price_per_seat', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('trips',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('passenger_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('direction', sa.Enum('bekobod_to_tashkent','tashkent_to_bekobod', name='tripdirection'), nullable=False),
        sa.Column('pickup_point', sa.String(300), nullable=False),
        sa.Column('dropoff_point', sa.String(300), nullable=False),
        sa.Column('trip_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('seats', sa.Integer(), server_default='1'),
        sa.Column('category', sa.Enum('passenger','passenger_small_cargo','cargo', name='tripcategory'), nullable=False, server_default='passenger'),
        sa.Column('car_type_preference', sa.Enum('any','sedan','minivan','cargo_van', name='cartype'), server_default='any'),
        sa.Column('price_per_seat', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('luggage', sa.Boolean(), server_default='false'),
        sa.Column('status', sa.Enum('active','accepted','in_progress','completed','cancelled','expired', name='tripstatus'), server_default='active'),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trips_id', 'trips', ['id'])
    op.create_index('ix_trips_status', 'trips', ['status'])


def downgrade():
    op.drop_table('trips')
    op.drop_table('pricing')
    op.drop_table('driver_profiles')
    op.drop_table('users')

"""LR4 privacy engineering: phone, privacy flags, consent, audit

Revision ID: a4c0f1e2d3b5
Revises: 834b1a697901
Create Date: 2026-11-04 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c0f1e2d3b5'
down_revision = '834b1a697901'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=32),
                                      nullable=True))
        batch_op.add_column(sa.Column('can_manage_privacy', sa.Boolean(),
                                      server_default=sa.false(),
                                      nullable=False))
        batch_op.add_column(sa.Column('anonymized_at', sa.DateTime(),
                                      nullable=True))

    op.create_table(
        'user_consent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('policy_version', sa.String(length=32), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=True),
        sa.Column('withdrawn_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'purpose',
                            name='uq_user_consent_purpose'))
    op.create_index('ix_user_consent_user_id', 'user_consent', ['user_id'])

    op.create_table(
        'consent_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=8), nullable=False),
        sa.Column('policy_version', sa.String(length=32), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_consent_event_user_id', 'consent_event', ['user_id'])

    op.create_table(
        'analytics_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_analytics_event_user_id', 'analytics_event',
                    ['user_id'])

    op.create_table(
        'marketing_dispatch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('campaign', sa.String(length=64), nullable=False),
        sa.Column('policy_version', sa.String(length=32), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_marketing_dispatch_user_id', 'marketing_dispatch',
                    ['user_id'])

    op.create_table(
        'audit_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('actor_ref', sa.String(length=32), nullable=False),
        sa.Column('subject_ref', sa.String(length=32), nullable=False),
        sa.Column('result', sa.String(length=16), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_audit_event_occurred_at', 'audit_event',
                    ['occurred_at'])


def downgrade():
    op.drop_index('ix_audit_event_occurred_at', table_name='audit_event')
    op.drop_table('audit_event')
    op.drop_index('ix_marketing_dispatch_user_id',
                  table_name='marketing_dispatch')
    op.drop_table('marketing_dispatch')
    op.drop_index('ix_analytics_event_user_id', table_name='analytics_event')
    op.drop_table('analytics_event')
    op.drop_index('ix_consent_event_user_id', table_name='consent_event')
    op.drop_table('consent_event')
    op.drop_index('ix_user_consent_user_id', table_name='user_consent')
    op.drop_table('user_consent')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('anonymized_at')
        batch_op.drop_column('can_manage_privacy')
        batch_op.drop_column('phone')

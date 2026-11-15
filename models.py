"""
Database models for the Barangay Health CMS.
"""
from datetime import date, datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from typing import Optional

db = SQLAlchemy()

# Purok/Zone Choices for Barangay
PUROK_CHOICES = [
    'Zone 1A-Danao',
    'Zone 1B-Mother of Devine Mercy village', 
    'Zone 2-Danao', 
    'Zone 3-Labapo',
    'Zone 4-Centro',
    'Zone 5-Mamis',
    'Zone 6-Tuling',
    'Zone 7-Camagon',
    'Zone 8-Saguing',
    'Zone 9-Camingawan'
]

# 1. User Authentication & RBAC Table
class User(db.Model, UserMixin):
    ROLE_CHOICES = ['Admin', 'Midwife', 'BHW']
    
    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password: str = db.Column(db.String(255), nullable=False)
    full_name: str = db.Column(db.String(150), nullable=True)
    role: str = db.Column(db.String(50), nullable=False, default='BHW')
    email: Optional[str] = db.Column(db.String(100), unique=True, nullable=True)
    contact_number: Optional[str] = db.Column(db.String(20), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    is_active: bool = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
    
    def has_role(self, *roles):
        return self.role in roles

# 2. Patient Management & Maternal Health
class Patient(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    full_name: str = db.Column(db.String(100), nullable=False, index=True)
    birth_date: datetime.date = db.Column(db.Date, nullable=False)
    address: Optional[str] = db.Column(db.String(200))
    email: Optional[str] = db.Column(db.String(120), nullable=True, index=True)
    contact_number: Optional[str] = db.Column(db.String(20))
    gender: str = db.Column(db.String(10), nullable=False)
    purok: str = db.Column(db.String(50), nullable=False, index=True)
    is_pregnant: bool = db.Column(db.Boolean, default=False, index=True)
    last_menstrual_period: Optional[datetime.date] = db.Column(db.Date, nullable=True)
    expected_delivery_date: Optional[datetime.date] = db.Column(db.Date, nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    consultations = db.relationship('Consultation', backref='patient', lazy=True, cascade='all, delete-orphan')
    
    @property
    def age(self):
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))

# 3. Consultation Records
class Consultation(db.Model):
    CONSULTATION_TYPES = ['General', 'Prenatal', 'Immunization', 'Follow-up', 'Emergency']
    
    id: int = db.Column(db.Integer, primary_key=True)
    patient_id: int = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False, index=True)
    health_worker_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    date: datetime = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    chief_complaint: str = db.Column(db.Text, nullable=False)
    diagnosis: str = db.Column(db.Text, nullable=False)
    notes: Optional[str] = db.Column(db.Text)
    consultation_type: str = db.Column(db.String(50), default='General')
    temperature: Optional[float] = db.Column(db.Float)
    blood_pressure_systolic: Optional[int] = db.Column(db.Integer)
    blood_pressure_diastolic: Optional[int] = db.Column(db.Integer)
    weight: Optional[float] = db.Column(db.Float)
    height: Optional[float] = db.Column(db.Float)
    respiratory_rate: Optional[int] = db.Column(db.Integer)
    health_worker = db.relationship('User', backref='consultations')
    __table_args__ = (
        db.Index('ix_consultation_patient_date', 'patient_id', 'date'),
        db.Index('ix_consultation_worker_date', 'health_worker_id', 'date'),
    )

# 4. Inventory Management
class InventoryItem(db.Model):
    CATEGORIES = ['Medicine', 'Supply', 'Equipment', 'Vaccine']
    
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False, unique=True, index=True)
    category: str = db.Column(db.String(50), nullable=False, default='Supply')
    quantity: int = db.Column(db.Integer, default=0, nullable=False)
    unit: Optional[str] = db.Column(db.String(20), default='piece')
    expiry_date: Optional[datetime.date] = db.Column(db.Date, nullable=True)
    min_stock_level: int = db.Column(db.Integer, default=10, nullable=False)
    price_per_unit: Optional[float] = db.Column(db.Float)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    dispensed_records = db.relationship('DispensedMedicine', backref='inventory_item', lazy=True, cascade='all, delete-orphan')
    
    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock_level
    
    @property
    def is_expired(self):
        return self.expiry_date and self.expiry_date < date.today()

# 5. Dispensed Medicine Tracking
class DispensedMedicine(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    consultation_id: int = db.Column(db.Integer, db.ForeignKey('consultation.id'), nullable=False, index=True)
    inventory_item_id: int = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False, index=True)
    quantity_dispensed: int = db.Column(db.Integer, nullable=False)
    dosage: Optional[str] = db.Column(db.String(100))
    instructions: Optional[str] = db.Column(db.String(255))
    route: Optional[str] = db.Column(db.String(50))
    frequency: Optional[str] = db.Column(db.String(50))
    duration: Optional[str] = db.Column(db.String(50))
    warnings: Optional[str] = db.Column(db.String(255))
    dispensed_by: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    date_dispensed: datetime = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    consultation = db.relationship('Consultation', backref='dispensed_medicines')
    health_worker = db.relationship('User', backref='dispensed_medicines')

# 6. Household Profiling (BHW Focus)
class HouseholdProfile(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    household_head_name: str = db.Column(db.String(100), nullable=False)
    purok: str = db.Column(db.String(50), nullable=False, index=True)
    address: str = db.Column(db.String(200), nullable=False)
    number_of_members: int = db.Column(db.Integer, nullable=False)
    water_source: Optional[str] = db.Column(db.String(100))
    sanitation_type: Optional[str] = db.Column(db.String(100))
    electricity: bool = db.Column(db.Boolean, default=False)
    contact_number: Optional[str] = db.Column(db.String(20))
    notes: Optional[str] = db.Column(db.Text)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by = db.relationship('User', backref='household_profiles')

# 7. Operation Timbang (OPT) (BHW Focus)
class OperationTimbang(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Standard Columns
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    weight_kg = db.Column(db.Float)
    height_cm = db.Column(db.Float)
    bmi = db.Column(db.Float)
    
    # Status Columns
    nutritional_status = db.Column(db.String(50)) 
    requires_followup = db.Column(db.Boolean, default=False)
    measurement_date = db.Column(db.DateTime, default=datetime.now)
    
    # 👇 ADD THIS MISSING LINE 👇
    notes = db.Column(db.Text) 
    # 👆 THIS WAS MISSING 👆

    # Relationships
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recorded_by = db.relationship('User', backref='opt_records')
    patient = db.relationship('Patient', backref='opt_records')
    __table_args__ = (
        db.Index('ix_opt_patient_measurement_date', 'patient_id', 'measurement_date'),
        db.Index('ix_opt_followup_measurement_date', 'requires_followup', 'measurement_date'),
    )

    def calculate_bmi(self):
        if self.weight_kg and self.height_cm:
            height_m = self.height_cm / 100
            self.bmi = round(self.weight_kg / (height_m ** 2), 2)
        return self.bmi

    def _get_age_years(self):
        if not self.patient or not self.patient.birth_date:
            return None
        today = date.today()
        age_days = (today - self.patient.birth_date).days
        return age_days / 365.25

    def _get_bmi_thresholds(self, age_years):
        if age_years is None:
            return {'under': 16.0, 'over': 23.0}
        if age_years < 2:
            return {'under': 14.0, 'over': 18.0}
        if age_years < 5:
            return {'under': 14.0, 'over': 17.0}
        if age_years < 10:
            return {'under': 13.5, 'over': 19.0}
        return {'under': 16.0, 'over': 23.0}
    
    def assess_nutritional_status(self):
        if self.bmi is None: self.calculate_bmi()

        age_years = self._get_age_years()
        thresholds = self._get_bmi_thresholds(age_years)
        under = thresholds['under']
        over = thresholds['over']

        if self.bmi < under:
            self.nutritional_status = 'At Risk (Underweight)'
            self.requires_followup = True
        elif self.bmi <= over:
            self.nutritional_status = 'Normal'
            self.requires_followup = False
        elif self.bmi <= over + 5:
            self.nutritional_status = 'Overweight'
            self.requires_followup = True
        else:
            self.nutritional_status = 'Obese'
            self.requires_followup = True

# 8. Prenatal Information (Midwife Focus)
class PrenatalRecord(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    patient_id: int = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False, index=True)
    weeks_of_pregnancy: int = db.Column(db.Integer, nullable=False)
    estimated_delivery_date: datetime.date = db.Column(db.Date, nullable=False, index=True)
    gravidity: int = db.Column(db.Integer, nullable=True)
    parity: int = db.Column(db.Integer, nullable=True)
    blood_type: Optional[str] = db.Column(db.String(10))
    rh_factor: Optional[str] = db.Column(db.String(10))
    previous_complications: Optional[str] = db.Column(db.Text)
    systolic_bp: Optional[int] = db.Column(db.Integer)
    diastolic_bp: Optional[int] = db.Column(db.Integer)
    weight_kg: Optional[float] = db.Column(db.Float)
    last_checkup: Optional[datetime] = db.Column(db.DateTime)
    next_checkup: Optional[datetime.date] = db.Column(db.Date)
    notes: Optional[str] = db.Column(db.Text)
    is_active: bool = db.Column(db.Boolean, default=True, index=True)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    patient = db.relationship('Patient', backref='prenatal_records')
    __table_args__ = (
        db.Index('ix_prenatal_patient_active', 'patient_id', 'is_active'),
        db.Index('ix_prenatal_active_delivery', 'is_active', 'estimated_delivery_date'),
    )
    
    @property
    def is_high_risk(self):
        return bool(self.notes and 'high risk' in self.notes.lower())

    def current_weeks_of_pregnancy(self):
        today = date.today()
        conception_start = self.estimated_delivery_date - timedelta(days=280)
        gestational_days = (today - conception_start).days
        weeks = gestational_days // 7
        return max(0, min(42, weeks))
    
    def days_until_delivery(self):
        from datetime import date as date_class
        today = date_class.today()
        return (self.estimated_delivery_date - today).days

# 9. Immunization Schedule (Midwife Focus)
class ImmunizationSchedule(db.Model):
    VACCINE_TYPES = ['BCG', 'Penta', 'Measles', 'Polio', 'OPV', 'Rotavirus', 'Pneumococcal']
    
    id: int = db.Column(db.Integer, primary_key=True)
    patient_id: int = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False, index=True)
    vaccine_name: str = db.Column(db.String(50), nullable=False)
    scheduled_date: datetime.date = db.Column(db.Date, nullable=False, index=True)
    age_in_months: int = db.Column(db.Integer, nullable=False)
    is_completed: bool = db.Column(db.Boolean, default=False, index=True)
    date_administered: Optional[datetime] = db.Column(db.DateTime)
    batch_number: Optional[str] = db.Column(db.String(50))
    administered_by_id: Optional[int] = db.Column(db.Integer, db.ForeignKey('user.id'))
    notes: Optional[str] = db.Column(db.Text)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('Patient', backref='immunization_schedule')
    administered_by = db.relationship('User', backref='administered_vaccines')
    __table_args__ = (
        db.Index('ix_immunization_completed_scheduled', 'is_completed', 'scheduled_date'),
        db.Index('ix_immunization_patient_completed', 'patient_id', 'is_completed'),
    )
    
    @property
    def is_overdue(self):
        from datetime import date as date_class
        return not self.is_completed and self.scheduled_date < date_class.today()

# 10. Audit Log & Notifications (System)
class AuditLog(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    user_id: Optional[int] = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action: str = db.Column(db.String(255), nullable=False, index=True)
    details: Optional[str] = db.Column(db.Text, nullable=True)
    ip_address: Optional[str] = db.Column(db.String(45), nullable=True)
    timestamp: datetime = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user = db.relationship('User', backref='audit_logs')

    @staticmethod
    def log_action(user_id, action, details=None, ip_address=None):
        log_entry = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip_address)
        db.session.add(log_entry)
        try: db.session.commit()
        except: db.session.rollback()
        return log_entry

class Notification(db.Model):
    NOTIFICATION_TYPES = ['low_stock', 'expired_item', 'expiring_soon', 'system_alert', 'appointment']
    id: int = db.Column(db.Integer, primary_key=True)
    user_id: Optional[int] = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    type: str = db.Column(db.String(50), nullable=False, index=True)
    title: str = db.Column(db.String(255), nullable=False)
    message: str = db.Column(db.Text, nullable=False)
    is_read: bool = db.Column(db.Boolean, default=False, index=True)
    related_item_id: Optional[int] = db.Column(db.Integer, nullable=True)
    related_item_type: Optional[str] = db.Column(db.String(50), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user = db.relationship('User', backref='notifications')
    __table_args__ = (
        db.Index('ix_notification_user_read_created', 'user_id', 'is_read', 'created_at'),
        db.Index('ix_notification_related_type_created', 'related_item_type', 'related_item_id', 'type', 'created_at'),
    )

    @staticmethod
    def create_notification(user_id, notification_type, title, message, related_item_id=None, related_item_type=None):
        notification = Notification(user_id=user_id, type=notification_type, title=title, message=message, related_item_id=related_item_id, related_item_type=related_item_type)
        db.session.add(notification)
        try: db.session.commit()
        except: db.session.rollback()
        return notification

    @classmethod
    def get_unread_count(cls, user_id=None):
        try:
            query = cls.query.filter_by(is_read=False)
            if user_id:
                query = query.filter((cls.user_id == user_id) | (cls.user_id.is_(None)))
            return query.count()
        except Exception:
            # Handle case where notification table doesn't have required columns
            return 0

    @classmethod
    def get_user_notifications(cls, user_id, limit=50):
        query = cls.query
        if user_id:
            query = query.filter((cls.user_id == user_id) | (cls.user_id.is_(None)))
        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def mark_as_read(cls, notification_id, user_id=None):
        notification = cls.query.get(notification_id)
        if notification and (user_id is None or notification.user_id in [None, user_id]):
            notification.is_read = True
            db.session.commit()
            return True
        return False
        
    @classmethod
    def check_and_create_low_stock_notifications(cls):
        low_stock_items = InventoryItem.query.filter(InventoryItem.quantity <= InventoryItem.min_stock_level).all()
        target_users = User.query.filter(User.role.in_(['Admin', 'Midwife'])).all()
        created_count = 0
        for item in low_stock_items:
            for target_user in target_users:
                exists = cls.query.filter_by(
                    user_id=target_user.id,
                    type='low_stock',
                    related_item_id=item.id,
                    related_item_type='inventory_item',
                    is_read=False
                ).first()
                if exists:
                    continue
                cls.create_notification(
                    user_id=target_user.id,
                    notification_type='low_stock',
                    title=f'Low stock: {item.name}',
                    message=f'{item.name} is running low ({item.quantity} {item.unit} left, minimum {item.min_stock_level}).',
                    related_item_id=item.id,
                    related_item_type='inventory_item'
                )
                created_count += 1
        return created_count
        
    @classmethod
    def check_and_create_expiry_notifications(cls):
        from datetime import date, timedelta

        today = date.today()
        soon_threshold = today + timedelta(days=30)

        expiring_or_expired_items = InventoryItem.query.filter(
            InventoryItem.expiry_date.isnot(None),
            InventoryItem.expiry_date <= soon_threshold
        ).all()
        target_users = User.query.filter(User.role.in_(['Admin', 'Midwife'])).all()

        created_count = 0
        for item in expiring_or_expired_items:
            is_expired = item.expiry_date < today
            notif_type = 'expired_item' if is_expired else 'expiring_soon'
            title = f'Expired item: {item.name}' if is_expired else f'Expiring soon: {item.name}'
            message = (
                f'{item.name} expired on {item.expiry_date:%b %d, %Y}.'
                if is_expired else
                f'{item.name} will expire on {item.expiry_date:%b %d, %Y}.'
            )

            for target_user in target_users:
                exists = cls.query.filter_by(
                    user_id=target_user.id,
                    type=notif_type,
                    related_item_id=item.id,
                    related_item_type='inventory_item',
                    is_read=False
                ).first()
                if exists:
                    continue

                cls.create_notification(
                    user_id=target_user.id,
                    notification_type=notif_type,
                    title=title,
                    message=message,
                    related_item_id=item.id,
                    related_item_type='inventory_item'
                )
                created_count += 1

        return created_count

# 11. Appointment System
class ScheduleSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    health_worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    health_worker = db.relationship('User', backref='schedule_slots')

class Appointment(db.Model):
    STATUSES = ['scheduled', 'completed', 'cancelled', 'no-show']
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False, index=True)
    health_worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='scheduled', index=True)
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    patient = db.relationship('Patient', backref='appointments')
    health_worker = db.relationship('User', backref='appointments')
    __table_args__ = (
        db.Index('ix_appointment_worker_date_time_status', 'health_worker_id', 'appointment_date', 'appointment_time', 'status'),
        db.Index('ix_appointment_date_status', 'appointment_date', 'status'),
    )
    
    @classmethod
    def check_conflict(cls, health_worker_id, appointment_date, appointment_time, duration_minutes=30):
        from datetime import datetime as dt, timedelta
        appointment_datetime = dt.combine(appointment_date, appointment_time)
        end_datetime = appointment_datetime + timedelta(minutes=duration_minutes)
        window_start = (appointment_datetime - timedelta(minutes=duration_minutes)).time()
        conflicting = cls.query.filter(
            cls.health_worker_id == health_worker_id,
            cls.appointment_date == appointment_date,
            cls.status.in_(['scheduled', 'completed']),
            cls.appointment_time >= window_start,
            cls.appointment_time < end_datetime.time(),
        ).first()
        if conflicting:
            return {'has_conflict': True, 'conflicting_appointment': conflicting, 'message': f'Conflict at {conflicting.appointment_time}'}
        return {'has_conflict': False, 'conflicting_appointment': None, 'message': 'Slot is available'}

# --- NEW FEATURE: COMMUNITY HEALTH EVENTS (BHW Compensation) ---
class CommunityEvent(db.Model):
    """
    Model for tracking community health events organized by BHWs.
    Examples: Mother's Classes, Feeding Programs, Dengue Awareness.
    """
    id: int = db.Column(db.Integer, primary_key=True)
    title: str = db.Column(db.String(150), nullable=False)
    event_date: datetime.date = db.Column(db.Date, nullable=False, index=True)
    location: str = db.Column(db.String(100), nullable=False)  # e.g., "Purok 1 Chapel"
    attendees_count: int = db.Column(db.Integer, default=0)
    topic: str = db.Column(db.String(100), nullable=False)  # e.g., "Nutrition", "Family Planning"
    notes: Optional[str] = db.Column(db.Text)
    
    # NEW: Optional Image Upload (Requested feature)
    image_filename: Optional[str] = db.Column(db.String(100), nullable=True)
    
    # Organizer
    organizer_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    organizer = db.relationship('User', backref='organized_events')
    
    def __repr__(self):
        return f'<CommunityEvent {self.title}>'
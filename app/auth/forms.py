from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError, EqualTo
from app.models import User
import bleach
import re

class LoginForm(FlaskForm):
    # User will log in with their Student Registration Number or Staff ID
    identifier = StringField('Student Registration Number or Staff ID', validators=[DataRequired()], 
                        filters=[lambda x: x.strip() if x else x])
    
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    # No filter here — we capitalize in validate_username so it is enforced even on lowercase input
    username = StringField('Full Name or Username', validators=[DataRequired(), Length(min=2, max=50)], filters=[lambda x: x.strip() if x else x])
    identifier = StringField('Student Registration Number or Staff ID', validators=[DataRequired(), Length(min=4, max=50)], filters=[lambda x: x.strip() if x else x])
    # No filter here — we lowercase and validate inside validate_email
    email = StringField('Email', validators=[DataRequired()], filters=[lambda x: x.strip() if x else x])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Regexp(r'^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[!@#$%^&*])', 
               message="Password must contain uppercase, lowercase, number, and special character.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('student', 'Student'), ('librarian', 'Librarian'), ('admin', 'Admin')], default='student')
    submit = SubmitField('Register')

    def validate_username(self, field):
        """Only letters, hyphens and apostrophes allowed. Auto-capitalise the first letter."""
        raw = bleach.clean(field.data.strip(), tags=[], strip=True)

        # Only allow letters, spaces, hyphens, apostrophes
        if not re.match(r"^[A-Za-z\s'\-]+$", raw):
            raise ValidationError(
                "Name may only contain letters, spaces, hyphens (-), or apostrophes (')."
                " No numbers or special characters are allowed."
            )

        # Auto-capitalise the first character; leave the rest as typed
        field.data = raw[0].upper() + raw[1:]

    def validate_identifier(self, field):
        field.data = bleach.clean(field.data, tags=[], strip=True)
        user = User.query.filter_by(identifier=field.data).first()
        if user:
            raise ValidationError('That ID is taken. Please choose a different one or log in.')

    def validate_email(self, field):
        raw = bleach.clean(field.data.strip(), tags=[], strip=True)

        # Step 1: Reject if ANY uppercase letter is present
        if any(c.isupper() for c in raw):
            raise ValidationError(
                'Email must be all lowercase. No uppercase letters are allowed (e.g. user@example.com).'
            )

        # Step 2: Check standard email format with valid extension
        email_pattern = r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.(com|org|net|edu|gov|io|co|uk|us|ac)$'
        if not re.match(email_pattern, raw):
            raise ValidationError(
                'Enter a valid email address (e.g. user@example.com). '
                'Must contain @, no uppercase, and a valid extension like .com or .org.'
            )

        # Step 3: Store cleaned value and check for duplicates
        field.data = raw
        user = User.query.filter_by(email=field.data).first()
        if user:
            raise ValidationError('That email is already registered. Please log in instead.')
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Regexp, Optional
from flask_wtf.file import FileField, FileAllowed, FileSize

class BookForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ])
    author = StringField('Author', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ])
    isbn = StringField('ISBN', validators=[
        DataRequired(), 
        Length(min=10, max=20),
        Regexp(r'^[0-9\-]+$', message="ISBN must contain only numbers and dashes.")
    ])
    genre = StringField('Genre', validators=[
        DataRequired(), 
        Length(min=2, max=50)
    ])
    book_type = SelectField('Book Type', choices=[('physical', 'Physical'), ('digital', 'Digital')], default='physical')
    file_path = FileField('Digital Book File', validators=[
        Optional(), 
        FileAllowed(['pdf', 'epub', 'txt'], 'Only PDF, EPUB, and TXT files are allowed!'),
        FileSize(max_size=5 * 1024 * 1024, message="File size must be under 5MB.")
    ])
    submit = SubmitField('Add Book')

from flask_wtf import FlaskForm
from wtforms import IntegerField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange, Optional


class BudgetingForm(FlaskForm):
    budget = IntegerField(
        'Total Budget',
        validators=[InputRequired(), NumberRange(min=1, message='Budget must be a positive number')]
    )
    projects = TextAreaField(
        'Projects',
        validators=[DataRequired()]
    )
    preferences = TextAreaField(
        'Voter Preferences',
        validators=[DataRequired()]
    )
    algorithm = SelectField(
        'Algorithm',
        choices=[
            ('gcr', 'BW-GCR-PB — satisfies Full Justified Representation (FJR)'),
            ('mes', 'BW-MES-PB — satisfies Extended Justified Representation (EJR)'),
            ('both', 'Compare Both Algorithms Side by Side'),
        ]
    )
    submit = SubmitField('Run Algorithm')

    # Random-fill helper fields
    rand_voters = IntegerField(
        'Number of Voters',
        validators=[Optional(), NumberRange(min=1, max=20)]
    )
    rand_projects = IntegerField(
        'Number of Projects',
        validators=[Optional(), NumberRange(min=1)]
    )
    rand_fill = SubmitField('Fill with Random Data')

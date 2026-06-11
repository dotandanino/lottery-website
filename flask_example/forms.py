from flask_wtf import FlaskForm
from wtforms import IntegerField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange, Optional


class BudgetingForm(FlaskForm):
    # IntegerField: renders as <input type="number">
    # InputRequired: fails if the field is empty (stricter than DataRequired for numbers)
    # NumberRange(min=1): rejects zero or negative budgets
    budget = IntegerField(
        'Total Budget',
        validators=[InputRequired(), NumberRange(min=1, message='Budget must be a positive number')]
    )

    # TextAreaField: renders as <textarea> — free-text input for multiple lines
    # DataRequired: fails if the field is empty or contains only whitespace
    projects = TextAreaField(
        'Projects',
        validators=[DataRequired()]
    )

    # Same as projects — one voter preference per line
    preferences = TextAreaField(
        'Voter Preferences',
        validators=[DataRequired()]
    )

    # SelectField: renders as <select> dropdown
    # choices: list of (value, label) pairs — value is what routes.py receives, label is what the user sees
    algorithm = SelectField(
        'Algorithm',
        choices=[
            ('gcr', 'BW-GCR-PB — satisfies Full Justified Representation (FJR)'),
            ('mes', 'BW-MES-PB — satisfies Extended Justified Representation (EJR)'),
            ('both', 'Compare Both Algorithms Side by Side'),
        ]
    )

    # SubmitField: renders as <input type="submit"> — triggers the main POST
    submit = SubmitField('Run Algorithm')

    # ── Random-fill helper fields ────────────────────────────────────────────
    # These fields belong to the separate random-fill form in demo.html.
    # Optional(): skips validation if the field is left empty

    # Number of voters to generate (capped at 20 because GCR grows exponentially)
    rand_voters = IntegerField(
        'Number of Voters',
        validators=[Optional(), NumberRange(min=1, max=20)]
    )

    # Number of projects to generate
    rand_projects = IntegerField(
        'Number of Projects',
        validators=[Optional(), NumberRange(min=1)]
    )

    # Second submit button — routes.py checks rand_fill.data to tell it apart from submit
    rand_fill = SubmitField('Fill with Random Data')

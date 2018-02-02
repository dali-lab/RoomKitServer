from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from flask import render_template


class RegisterForm(FlaskForm):
    project = StringField('Project Name', validators=[DataRequired()])
    email = StringField('Your email', validators=[DataRequired()])
    register = SubmitField('Register')


class ResetTrainingForm(FlaskForm):
    project = StringField('Project Name', validators=[DataRequired()])
    email = StringField('Your email', validators=[DataRequired()])
    reset = SubmitField('RESET TRAINING')


def render_register_page():
    form = RegisterForm()
    return render_template('register.html', form=form)


def render_reset_training_page():
    form = RegisterForm()
    return render_template('reset_training.html', form=form)

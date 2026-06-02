from flask import Flask

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fair-lotteries-pb-2024-secret'

from flask_example import routes

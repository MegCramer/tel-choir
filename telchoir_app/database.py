from flask_sqlalchemy import SQLAlchemy
from telchoir_app import create_app


app = create_app()
db = SQLAlchemy(app)

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from pymongo import MongoClient
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from datetime import datetime
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-for-forms'

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@db_sql:5432/cars_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

mongo_client = MongoClient('mongodb://db_web:27017/')
mongo_db = mongo_client['cars_database']
comments_collection = mongo_db['comments']

class Car(db.Model):
    __tablename__ = 'cars'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    brand = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric, db.CheckConstraint('price > 0'))
    stock = db.Column(db.Integer, db.CheckConstraint('stock >= 0'))


class CarForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    brand = StringField('Марка', validators=[DataRequired()])
    description = TextAreaField('Описание')
    price = DecimalField('Цена', validators=[DataRequired(), NumberRange(min=0.01)])
    stock = IntegerField('Количество на складе', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Сохранить автомобиль')


class CommentForm(FlaskForm):
    author = StringField('Автор', validators=[Optional()])
    text = TextAreaField('Текст отзыва', validators=[DataRequired()])
    rating = SelectField('Оценка', choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')], coerce=int)
    submit = SubmitField('Оставить отзыв')


@app.route('/')
def index():
    cars = Car.query.all()
    return render_template('index.html', cars=cars)

@app.route('/cars/new', methods=['GET', 'POST'])
def add_car():
    form = CarForm()
    if form.validate_on_submit():
        new_car = Car(
            name=form.name.data,
            brand=form.brand.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data
        )
        db.session.add(new_car)
        db.session.commit()
        return redirect(url_for('index'))
    print(form.errors)
    return render_template('add_car.html', form=form)


@app.route('/cars/<int:product_id>', methods=['GET', 'POST'])
def car_detail(product_id):
    car = Car.query.get_or_404(product_id)
    form = CommentForm()

    if form.validate_on_submit():
        comment = {
            "product_id": product_id,
            "author": form.author.data if form.author.data else "Аноним",
            "text": form.text.data,
            "rating": form.rating.data,
            "created_at": datetime.now()
        }
        comments_collection.insert_one(comment)
        return redirect(url_for('car_detail', product_id=product_id))

    comments = list(comments_collection.find({"product_id": product_id}).sort("created_at", -1))
    return render_template('car_detail.html', car=car, form=form, comments=comments)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').strip()
    min_rating = request.args.get('min_rating', type=int)

    if not query and not min_rating:
        return render_template('search.html', message="Пожалуйста, введите запрос для поиска.")

    sql_query = Car.query
    if query:
        sql_query = sql_query.filter(Car.name.ilike(f'%{query}%'))
    cars = sql_query.all()

    results = []
    for car in cars:
        car_comments = list(comments_collection.find({"product_id": car.id}))
        if car_comments:
            avg_rating = sum(c['rating'] for c in car_comments) / len(car_comments)
        else:
            avg_rating = 0
        if min_rating is None or avg_rating >= min_rating:
            results.append({
                'id': car.id,
                'name': car.name,
                'price': car.price,
                'avg_rating': round(avg_rating, 2) if avg_rating > 0 else "Нет оценок"
            })

    return render_template('search.html', results=results, query=query, min_rating=min_rating)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

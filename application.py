import os
import requests

from flask import Flask, session, render_template, request, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

susername = None

@app.route("/")
def index():
    session.pop('susername', None)
    return render_template("index.html")

@app.route("/", methods=["POST"])
def register():
    regusername = request.form.get("regusername")
    regname = request.form.get("regname")
    regpassword = request.form.get("regpassword")

    if regname == "" or regusername == "" or regpassword == "":
        reg_message = "<div class=\"alert alert-warning\" role=\"alert\">Please fill all the camps.</div>"
        return render_template("index.html", reg_message = reg_message)


    if db.execute("select username from users where :username = username", {"username": regusername}).rowcount != 0:
        reg_message = "<div class=\"alert alert-warning\" role=\"alert\">" + regusername + "is already used, try again.</div>"
        return render_template("index.html", reg_message = reg_message)

    regpassword = hash(regpassword)

    db.execute("INSERT INTO users (username,password) VALUES (:username, :password)",
        {"username": regusername , "password": regpassword})
    db.commit()
    reg_message = "<div class=\"alert alert-success\" role=\"alert\"> Welcome " + regname + ", now you can login.</div>"
    return render_template("index.html", reg_message = reg_message)


@app.route("/main", methods=["GET", "POST"])
def login():
    if request.method == 'GET':
        return render_template("index.html")
    if session.get("susername") is None:
        if request.method == "POST":
            logusername = request.form.get("logusername")
            logpassword = request.form.get('logpassword')
            logpassword = hash(logpassword)
            if db.execute("select username, password from users where username = :username and password = :password", {"username": logusername  , "password": logpassword}).rowcount == 0:
                message = "Wrong password or username!"
                return render_template("index.html", message = message )
            session['susername'] = logusername
    logusername = session['susername']
    books = db.execute("SELECT * FROM books LIMIT 12").fetchall()
    return render_template('main.html', username = logusername, name = logusername, books = books)


@app.route("/main/seach", methods=["POST"])
def search():
    searchstring = request.form.get("string")
    message = "You are searching; "  + "\'" + searchstring + "\'"
    username = session['susername']
    rbooks = db.execute("SELECT * FROM books where (isbn LIKE " + "\'%" + searchstring + "%\')" + " or (author LIKE " + "\'%" + searchstring + "%\')" + " or (tittle LIKE " + "\'%" + searchstring + "%\')").fetchall()
    return render_template("search.html", string = message, username = username, name = username, rbooks = rbooks)

@app.route("/main/book/<int:book_id>")
def book(book_id):
    username = session['susername']
    book = db.execute("SELECT * FROM books where id = :id", {"id": book_id}).fetchone()
    reviews = db.execute("SELECT * FROM reviews where bookid = :id", {"id": book_id}).fetchall()

    isbn = db.execute("SELECT isbn FROM books where id = :id", {"id": book_id}).fetchone()
    res = requests.get('https://www.goodreads.com/book/review_counts.json', params={"key": "TMdSMx0CMdpdnoPJHKqOA", "isbns": isbn})
    if res.status_code != 200:
        raise Exception("ERROR: API request unsuccessful.")
    res = res.json()
    rev_count = res['books'][0]['work_ratings_count']
    average_rating = res['books'][0]['average_rating']
    return render_template("book.html", username = username, name = username, book = book, reviews = reviews, rev_count = rev_count, rev_avg = average_rating)

@app.route("/main/book/<int:book_id>", methods=["POST"])
def review(book_id):
    book = db.execute("SELECT * FROM books where id = :id", {"id": book_id}).fetchone()
    username = session['susername']
    if request.method == "POST":
        if db.execute("SELECT * FROM reviews where username = :username and bookid = :id", {'username': username, "id": book_id}).rowcount > 0:
            message = "You can not review this book again."
            book = book
            reviews = db.execute("SELECT * FROM reviews where bookid = :id", {"id": book_id}).fetchall()
            return render_template("book.html", username = username, name = username, book = book, reviews = reviews, allow = message)
        book = book
        value = request.form.get("rate")
        if value is None:
            value = 0
        review = request.form.get("review")
        db.execute("INSERT INTO reviews (bookid, username, rate, review) VALUES (:id, :username, :rate, :review)",
            {"id": book_id, "username": username, "rate": value, "review": review})
        db.commit()
        reviews = db.execute("SELECT * FROM reviews where bookid = :id", {"id": book_id}).fetchall()

        isbn = db.execute("SELECT isbn FROM books where id = :id", {"id": book_id}).fetchone()
        res = requests.get('https://www.goodreads.com/book/review_counts.json', params={"key": "TMdSMx0CMdpdnoPJHKqOA", "isbns": isbn})
        if res.status_code != 200:
            raise Exception("ERROR: API request unsuccessful.")
        res = res.json()
        rev_count = res['books'][0]['work_ratings_count']
        average_rating = res['books'][0]['average_rating']
        return render_template("book.html", rusername = username,book = book, rate = value, review = review, reviews = reviews, rev_count = rev_count, rev_avg = average_rating)
    else:
        return render_template('main.html')

@app.route("/")
def logout():
    session.pop('susername', None)
    return render_template("index.html")

@app.route("/api/<isbn>", methods=["GET"])
def json_api(isbn):
    if request.method == 'GET':
        book = db.execute("SELECT * FROM books where isbn = :isbn", {'isbn': isbn}).fetchone()
        if book is None:
            return jsonify({"error": "Invalid ISBN"}), 404
        review = db.execute("select round(count(bookid),0) as rc, round(avg(rate),2) as ra from reviews where bookid in (SELECT id FROM books WHERE isbn = :isbn)", {'isbn': isbn}).fetchone()
        rc = int(review.rc)
        ra = float(review.ra)
        return jsonify({
                "title": book.tittle,
                "author": book.author,
                "year": book.year,
                "isbn": book.isbn,
                "review_count": rc,
                "average_score": ra
            })

    pass

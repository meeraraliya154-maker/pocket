import os
import time
import sqlite3
import hashlib

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    Request,
    Form,
    UploadFile,
    File
)

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from google import genai
from google.genai import types

from services.product_service import get_home_products


# =========================
# LOAD ENVIRONMENT
# =========================

load_dotenv()


# =========================
# FASTAPI
# =========================

app = FastAPI(
    title="PocketSmart AI"
)


# =========================
# STATIC FILES
# =========================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

STATIC_DIR = os.path.join(
    BASE_DIR,
    "static"
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)


# =========================
# GEMINI
# =========================

api_key = os.getenv(
    "GEMINI_API_KEY"
)

client = genai.Client(
    api_key=api_key
)


# =========================
# TEMPLATES
# =========================

templates = Jinja2Templates(
    directory="services/models/templates"
)


# =========================
# DATABASE
# =========================

DATABASE = "pocketsmart.db"


def init_database():

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            planner TEXT,
            details TEXT,
            recommendation TEXT
        )
    """)

    connection.commit()
    connection.close()


init_database()


# =========================
# PASSWORD HASH
# =========================

def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# =========================
# SAVE HISTORY
# =========================

def save_history(
    request,
    planner,
    details,
    recommendation
):

    email = request.cookies.get(
        "user_email"
    )

    if not email:
        return

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO history
        (
            user_email,
            planner,
            details,
            recommendation
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            email,
            planner,
            details,
            recommendation
        )
    )

    connection.commit()
    connection.close()


# =========================
# HOME
# =========================

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={}
    )


# =========================
# GEMINI TEST
# =========================

@app.get("/test-gemini")
def test_gemini():

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=
        "Say hello to PocketSmart AI in one short sentence."
    )

    return {
        "gemini_response": response.text
    }


# =========================
# REGISTER PAGE
# =========================

@app.get("/register")
def register_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={}
    )


# =========================
# REGISTER
# =========================

@app.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                hash_password(password)
            )
        )

        connection.commit()

    except sqlite3.IntegrityError:

        connection.close()

        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error":
                "Email already registered. Please login."
            }
        )

    connection.close()

    return RedirectResponse(
        url="/login",
        status_code=303
    )


# =========================
# LOGIN PAGE
# =========================

@app.get("/login")
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


# =========================
# LOGIN
# =========================

@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT name, email
        FROM users
        WHERE email = ?
        AND password = ?
        """,
        (
            email,
            hash_password(password)
        )
    )

    user = cursor.fetchone()

    connection.close()

    if user is None:

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error":
                "Invalid email or password."
            }
        )

    response = RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    response.set_cookie(
        key="user_email",
        value=email,
        httponly=True
    )

    return response


# =========================
# LOGOUT
# =========================

@app.get("/logout")
def logout():

    response = RedirectResponse(
        url="/",
        status_code=303
    )

    response.delete_cookie(
        "user_email"
    )

    return response
# =========================
# FORGOT PASSWORD PAGE
# =========================

@app.get("/forgot-password")
def forgot_password_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={}
    )


# =========================
# FORGOT PASSWORD
# =========================

@app.post("/forgot-password")
def forgot_password(
    request: Request,
    email: str = Form(...),
    new_password: str = Form(...)
):

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    user = cursor.fetchone()

    if not user:

        connection.close()

        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={
                "error":
                "Email not found. Please check your email."
            }
        )

    cursor.execute(
        """
        UPDATE users
        SET password = ?
        WHERE email = ?
        """,
        (
            hash_password(new_password),
            email
        )
    )

    connection.commit()
    connection.close()

    return RedirectResponse(
        url="/login",
        status_code=303
    )

# =========================
# DASHBOARD
# =========================

@app.get("/dashboard")
def dashboard(request: Request):

    email = request.cookies.get(
        "user_email"
    )

    if not email:

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT name, email
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    user = cursor.fetchone()

    connection.close()

    if not user:

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "name": user[0],
            "email": user[1]
        }
    )


# =========================
# HISTORY
# =========================

@app.get("/history")
def history(request: Request):

    email = request.cookies.get(
        "user_email"
    )

    if not email:

        return RedirectResponse(
            url="/login",
            status_code=303
        )

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            planner,
            details,
            recommendation
        FROM history
        WHERE user_email = ?
        ORDER BY id DESC
        """,
        (email,)
    )

    records = cursor.fetchall()

    connection.close()

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "history": records
        }
    )


# =========================
# HOME INTERIOR PLANNER
# =========================

@app.get("/home-planner")
def home_planner(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="home_planner.html",
        context={}
    )


# =========================
# HOME INTERIOR GENERATION
# =========================

@app.post("/generate-home")
def generate_home(
    request: Request,
    budget: int = Form(...),
    room: str = Form(...),
    items: int = Form(...),
    style: str = Form(...)
):

    # -------------------------
    # PRODUCT DATA
    # -------------------------

    products = get_home_products(
        room=room,
        style=style,
        budget=budget
    )


    # -------------------------
    # PRODUCT SUMMARY
    # -------------------------

    product_text = ""

    for product in products:

        product_text += (
            f"\n- {product['name']}"
            f" | ₹{product['price']}"
            f" | {product['source']}"
        )


    if not product_text:

        product_text = (
            "\nNo affordable products found."
        )


    # -------------------------
    # GEMINI PROMPT
    # -------------------------

    prompt = f"""
You are PocketSmart AI.

Create an affordable home interior plan.

User details:

Budget: ₹{budget}
Room: {room}
Number of Items: {items}
Style: {style}

Available affordable products:

{product_text}

Create a simple recommendation.

Include:

1. Recommended items
2. Estimated price
3. Total estimated cost
4. Money-saving suggestions
5. Style suggestions

Use the available products when suitable.

Do not exceed the user's budget.

Clearly explain that prices are estimated
and may vary.
"""


    # -------------------------
    # GEMINI
    # -------------------------

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    recommendation = response.text


    # -------------------------
    # DETAILS
    # -------------------------

    details = (
        f"Budget: ₹{budget} | "
        f"Room: {room} | "
        f"Items: {items} | "
        f"Style: {style}"
    )


    # -------------------------
    # HISTORY
    # -------------------------

    save_history(
        request,
        "Home Interior",
        details,
        recommendation
    )


    # -------------------------
    # RESULT PAGE
    # -------------------------

    return templates.TemplateResponse(
        request=request,
        name="home_result.html",
        context={
            "budget": budget,
            "room": room,
            "items": items,
            "style": style,
            "recommendations": recommendation,
            "products": products
        }
    )


# =========================
# PARTY PLANNER
# =========================

@app.get("/party-planner")
def party_planner(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="party_planner.html",
        context={}
    )


# =========================
# PARTY GENERATION
# =========================

@app.post("/generate-party")
def generate_party(
    request: Request,
    budget: int = Form(...),
    guests: int = Form(...),
    event_type: str = Form(...),
    venue: str = Form(...)
):

    prompt = f"""
You are PocketSmart AI.

Create a practical party budget plan.

Budget: ₹{budget}
Guests: {guests}
Event: {event_type}
Venue: {venue}

Allocate budget for:

1. Food
2. Decoration
3. Entertainment
4. Venue
5. Other expenses

Include estimated amounts and money-saving suggestions.

Keep the total within the budget.
"""

    response = None

    for attempt in range(3):

        try:

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            break

        except Exception:

            if attempt < 2:
                time.sleep(5)

            else:

                return templates.TemplateResponse(
                    request=request,
                    name="party_result.html",
                    context={
                        "budget": budget,
                        "guests": guests,
                        "event_type": event_type,
                        "venue": venue,
                        "recommendations":
                        "⚠️ Gemini AI is temporarily busy. Please try again."
                    }
                )

    recommendation = response.text

    details = (
        f"Budget: ₹{budget} | "
        f"Guests: {guests} | "
        f"Event: {event_type} | "
        f"Venue: {venue}"
    )

    save_history(
        request,
        "Party Planner",
        details,
        recommendation
    )

    return templates.TemplateResponse(
        request=request,
        name="party_result.html",
        context={
            "budget": budget,
            "guests": guests,
            "event_type": event_type,
            "venue": venue,
            "recommendations": recommendation
        }
    )


# =========================
# JEWELRY PLANNER
# =========================

@app.get("/jewelry-planner")
def jewelry_planner(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="jewelry_planner.html",
        context={}
    )


# =========================
# JEWELRY GENERATION
# =========================

@app.post("/generate-jewelry")
async def generate_jewelry(
    request: Request,
    budget: int = Form(...),
    occasion: str = Form(...),
    style: str = Form(...),
    outfit_color: str = Form(...),
    outfit_image: UploadFile = File(None)
):

    prompt = f"""
You are PocketSmart AI.

Recommend jewelry based on:

Budget: ₹{budget}
Occasion: {occasion}
Preferred Style: {style}
Outfit Colour: {outfit_color}

Include:

1. Recommended jewelry
2. Estimated price
3. Why it matches
4. Suitable metal or colour
5. Money-saving suggestions

Keep recommendations within the budget.

If an outfit image is provided,
analyze its visible colour and style
to improve the recommendation.

Do not identify the person in the image.
"""

    contents = [prompt]

    if (
        outfit_image is not None
        and outfit_image.filename
    ):

        image_data = await outfit_image.read()

        contents.append(
            types.Part.from_bytes(
                data=image_data,
                mime_type=outfit_image.content_type
            )
        )

    response = None

    for attempt in range(3):

        try:

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=contents
            )

            break

        except Exception:

            if attempt < 2:
                time.sleep(5)

            else:

                return templates.TemplateResponse(
                    request=request,
                    name="jewelry_result.html",
                    context={
                        "budget": budget,
                        "occasion": occasion,
                        "style": style,
                        "outfit_color": outfit_color,
                        "recommendations":
                        "⚠️ Gemini AI is temporarily busy. Please try again."
                    }
                )

    recommendation = response.text

    details = (
        f"Budget: ₹{budget} | "
        f"Occasion: {occasion} | "
        f"Style: {style} | "
        f"Outfit Colour: {outfit_color}"
    )

    save_history(
        request,
        "Jewelry Recommendation",
        details,
        recommendation
    )

    return templates.TemplateResponse(
        request=request,
        name="jewelry_result.html",
        context={
            "budget": budget,
            "occasion": occasion,
            "style": style,
            "outfit_color": outfit_color,
            "recommendations": recommendation
        }
    )
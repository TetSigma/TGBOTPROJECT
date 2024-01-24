

import sqlite3
from aiogram import types
from loader import bot, dp
from aiogram.dispatcher.filters import Command, Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.types import Message

# Database initialization
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

# Create tables if not exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        name TEXT,
        price INTEGER,
        category TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        purchase_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    )
''')
conn.commit()


class Registration(StatesGroup):
    waiting_for_username = State()
    waiting_for_balance = State()

# Start command handler
@dp.message_handler(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    # Check if user already registered
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()

    if existing_user:
        await message.answer("You are already registered.")
    else:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Register", callback_data="register"))
        await message.answer("Click the button below to register:", reply_markup=keyboard)


@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith("register"))
async def register_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await Registration.waiting_for_username.set()
    await bot.send_message(callback_query.from_user.id, "Please enter your username:")
    await Registration.waiting_for_username.set()

# Handle username input
@dp.message_handler(state=Registration.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    username = message.text
    user_id = message.from_user.id

    # Save username and proceed to balance input
    await state.update_data(username=username)
    await message.answer(f"Username set to {username}. Please enter your initial balance:")

    await Registration.waiting_for_balance.set()

# Handle balance input
@dp.message_handler(state=Registration.waiting_for_balance)
async def process_balance(message: types.Message, state: FSMContext):
    try:
        balance = int(message.text)
    except ValueError:
        await message.answer("Please enter a valid number for balance.")
        return

    user_data = await state.get_data()
    username = user_data['username']
    user_id = message.from_user.id

    # Insert user into the database
    cursor.execute('INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)',
                   (user_id, username, balance))
    conn.commit()

    await state.finish()
    await message.answer(f"Registration successful! Your balance is {balance}.")



class Shop(StatesGroup):
    waiting_for_product_choice = State()

# Command to display shop products
@dp.message_handler(Command("shop"))
async def cmd_shop(message: Message, state: FSMContext):
    # Retrieve products from the database
    cursor.execute('SELECT product_id, name, price FROM products')
    products = cursor.fetchall()

    if not products:
        await message.answer("No products available in the shop.")
        return

    # Create inline keyboard with products and prices
    keyboard = InlineKeyboardMarkup()
    for product_id, name, price in products:
        keyboard.add(InlineKeyboardButton(f"{name} - {price}", callback_data=f"buy_product_{product_id}"))

    await message.answer("Select a product to add to your cart:", reply_markup=keyboard)
    await Shop.waiting_for_product_choice.set()

# Handle product selection for adding to cart
@dp.callback_query_handler(lambda query: query.data.startswith('buy_product_'), state=Shop.waiting_for_product_choice)
async def process_buy_product(callback_query: types.CallbackQuery, state: FSMContext):
    product_id = int(callback_query.data.split('_')[2])
    user_id = callback_query.from_user.id

    # Retrieve user balance from the database
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    user_balance = cursor.fetchone()[0]

    # Retrieve product details
    cursor.execute('SELECT name, price FROM products WHERE product_id = ?', (product_id,))
    product_name, product_price = cursor.fetchone()

    # Check if user has enough balance to buy the product
    if user_balance < product_price:
        await bot.send_message(user_id, "Insufficient balance to buy this product.")
        await state.finish()

        return

    # Deduct the product price from user balance
    new_balance = user_balance - product_price
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    conn.commit()

    # Save the purchase in the database
    cursor.execute('INSERT INTO purchases (user_id, product_id) VALUES (?, ?)', (user_id, product_id))
    conn.commit()

    await bot.send_message(user_id, f"Product '{product_name}' added to your cart. Remaining balance: {new_balance}")
    await state.finish()

# Command to view the cart
@dp.message_handler(Command("view_cart"))
async def cmd_view_cart(message: Message):
    user_id = message.from_user.id

    # Retrieve user's cart from the database
    cursor.execute('''
        SELECT products.name, products.price
        FROM purchases
        JOIN products ON purchases.product_id = products.product_id
        WHERE purchases.user_id = ?
    ''', (user_id,))
    cart_items = cursor.fetchall()

    if not cart_items:
        await message.answer("Your cart is empty.")
    else:
        cart_text = "\n".join([f"{item[0]} - {item[1]}" for item in cart_items])
        await message.answer(f"Your cart:\n{cart_text}")
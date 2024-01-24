import sqlite3
from aiogram import types
from loader import bot, dp
from aiogram.dispatcher.filters import Command, Text
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton



conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

class AdminPanel(StatesGroup):
    waiting_for_action = State()
    waiting_for_user_id = State()
    waiting_for_balance_change = State()
    waiting_for_product_info = State()

@dp.message_handler(Command("admin"))
async def cmd_admin_panel(message: types.Message):
    user_id = message.from_user.id

    # Check if the user is an admin
    cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    print(result)

    if result and result[0] == 1:
        # If admin, show the admin panel options
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Ban User", callback_data="ban_user"))
        keyboard.add(InlineKeyboardButton("Add Admin", callback_data="add_admin"))
        keyboard.add(InlineKeyboardButton("Edit User Balance", callback_data="edit_balance"))
        keyboard.add(InlineKeyboardButton("Add Product", callback_data="add_product"))

        await message.answer("Admin Panel", reply_markup=keyboard)
        await AdminPanel.waiting_for_action.set()
    else:
        await message.answer("You are not authorized to access the admin panel.")

@dp.callback_query_handler(lambda query: query.data == 'ban_user', state=AdminPanel.waiting_for_action)
async def ban_user_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    # Retrieve all users from the database
    cursor.execute('SELECT user_id, username FROM users')
    users = cursor.fetchall()

    if not users:
        await bot.send_message(callback_query.from_user.id, "No users found.")
        return

    # Create inline keyboard with usernames
    keyboard = InlineKeyboardMarkup()
    for user_id, username in users:
        keyboard.add(InlineKeyboardButton(username, callback_data=f"ban_user_{user_id}"))
    keyboard.add(InlineKeyboardButton(text='Cancel', callback_data='cancel'))
    await AdminPanel.waiting_for_user_id.set()
    await bot.send_message(callback_query.from_user.id, "Select a user to ban:", reply_markup=keyboard)

# Handle user selection for banning
@dp.callback_query_handler(lambda query: query.data.startswith('ban_user_'), state=AdminPanel.waiting_for_user_id)
async def process_user_for_ban(callback_query: types.CallbackQuery, state: FSMContext):
    user_id_to_ban = int(callback_query.data.split('_')[2])

    # Delete the user record from the database
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id_to_ban,))
    conn.commit()

    await state.finish()
    await bot.send_message(callback_query.from_user.id, f"User with ID {user_id_to_ban} has been banned and their record deleted.")



# Handle user ID input for banning
@dp.message_handler(state=AdminPanel.waiting_for_user_id)
async def process_user_id_for_ban(message: types.Message, state: FSMContext):
    user_id_to_ban = message.text

    # Check if the user to be banned exists
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id_to_ban,))
    user_to_ban = cursor.fetchone()

    if user_to_ban:
        # Ban the user by updating the database
        cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id_to_ban,))
        conn.commit()

        await state.finish()
        await message.answer(f"User with ID {user_id_to_ban} has been banned.")
    else:
        await message.answer(f"User with ID {user_id_to_ban} not found. Please enter a valid user ID.")



@dp.callback_query_handler(lambda query: query.data == 'add_admin', state=AdminPanel.waiting_for_action)
async def add_admin_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    # Retrieve all non-admin users from the database
    cursor.execute('SELECT user_id, username FROM users WHERE is_admin = 0')
    users = cursor.fetchall()

    if not users:
        await bot.send_message(callback_query.from_user.id, "No eligible users found.")
        return

    # Create inline keyboard with usernames
    keyboard = InlineKeyboardMarkup()
    for user_id, username in users:
        keyboard.add(InlineKeyboardButton(username, callback_data=f"add_admin_{user_id}"))
    keyboard.add(InlineKeyboardButton(text='Cancel', callback_data='cancel'))
    await AdminPanel.waiting_for_user_id.set()
    await bot.send_message(callback_query.from_user.id, "Select a user to promote to admin:", reply_markup=keyboard)

# Handle user selection for promoting to admin
@dp.callback_query_handler(lambda query: query.data.startswith('add_admin_'), state=AdminPanel.waiting_for_user_id)
async def process_user_for_admin(callback_query: types.CallbackQuery, state: FSMContext):
    user_id_to_promote = int(callback_query.data.split('_')[2])

    # Update the user status to admin in the database
    cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id_to_promote,))
    conn.commit()

    await state.finish()
    await bot.send_message(callback_query.from_user.id, f"User with ID {user_id_to_promote} has been promoted to admin.")

@dp.callback_query_handler(lambda query: query.data == 'edit_balance', state=AdminPanel.waiting_for_action)
async def edit_balance_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    # Retrieve all users from the database
    cursor.execute('SELECT user_id, username, balance FROM users')
    users = cursor.fetchall()

    if not users:
        await bot.send_message(callback_query.from_user.id, "No users found.")
        return

    # Create inline keyboard with usernames
    keyboard = InlineKeyboardMarkup()
    for user_id, username, balance in users:
        keyboard.add(InlineKeyboardButton(text=f"{username} - Balance: {balance}", callback_data=f"edit_balance_{user_id}"))
    keyboard.add(InlineKeyboardButton(text='Cancel', callback_data='cancel'))
    await AdminPanel.waiting_for_user_id.set()
    await bot.send_message(callback_query.from_user.id, "Select a user to edit balance:", reply_markup=keyboard)

# Handle user selection for editing balance
@dp.callback_query_handler(lambda query: query.data.startswith('edit_balance_'), state=AdminPanel.waiting_for_user_id)
async def process_user_for_balance_edit(callback_query: types.CallbackQuery, state: FSMContext):
    user_id_to_edit = int(callback_query.data.split('_')[2])

    # Ask the admin to enter the new balance
    await bot.send_message(callback_query.from_user.id, f"Enter the new balance for user with ID {user_id_to_edit}:")
    await AdminPanel.waiting_for_balance_change.set()
    await state.update_data(user_id_to_edit=user_id_to_edit)

# Handle balance input for editing
@dp.message_handler(state=AdminPanel.waiting_for_balance_change)
async def process_balance_for_edit(message: types.Message, state: FSMContext):
    try:
        new_balance = int(message.text)
    except ValueError:
        await message.answer("Please enter a valid number for the new balance.")
        return

    user_data = await state.get_data()
    user_id_to_edit = user_data['user_id_to_edit']

    # Update the user balance in the database
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id_to_edit))
    conn.commit()

    await state.finish()
    await message.answer(f"Balance for user with ID {user_id_to_edit} has been updated to {new_balance}.")

@dp.callback_query_handler(lambda query: query.data == 'add_product', state=AdminPanel.waiting_for_action)
async def add_product_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)

    await AdminPanel.waiting_for_product_info.set()
    await bot.send_message(callback_query.from_user.id, "Enter the product name and price in the following format: <product_name> <price>")

# Handle product information input
@dp.message_handler(state=AdminPanel.waiting_for_product_info)
async def process_product_info(message: types.Message, state: FSMContext):
    product_info = message.text.split()

    if len(product_info) != 2:
        await message.answer("Invalid input format. Please enter the product name and price separated by a space.")
        return

    product_name, price_str = product_info
    try:
        price = float(price_str)
    except ValueError:
        await message.answer("Invalid price format. Please enter a valid numerical price.")
        return

    # Insert the new product into the database
    cursor.execute('INSERT INTO products (name, price) VALUES (?, ?)', (product_name, price))
    conn.commit()

    await state.finish()
    await message.answer(f"Product '{product_name}' with price {price} has been added.")




@dp.callback_query_handler(lambda query: query.data == 'cancel', state='*')
async def cancel_ban_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.send_message(callback_query.from_user.id, "Cancelled")

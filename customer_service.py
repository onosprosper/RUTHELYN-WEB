import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
import webbrowser
import urllib.parse

# ==========================================
# RUTHELYN COLLECTIONS CUSTOMER SERVICE
# ==========================================

BUSINESS_NAME = "RUTHELYN COLLECTIONS"
PHONE_NUMBER = "08125506022"
PHONE_NUMBER = "08153984064"
WHATSAPP_NUMBER = "2348125506022"


# ==========================================
# OPEN WHATSAPP
# ==========================================

def open_whatsapp():
    message = f"Hello {BUSINESS_NAME}, I need assistance with your products."

    url = (
        f"https://wa.me/{WHATSAPP_NUMBER}"
        f"?text={urllib.parse.quote(message)}"
    )

    webbrowser.open(url)


# ==========================================
# BOT RESPONSES
# ==========================================

def get_response(message):
    msg = message.lower()

    if any(x in msg for x in ["hello", "hi", "hey"]):
        return (
            f"Hello! Welcome to {BUSINESS_NAME}. 😊\n"
            "How can we help you today?"
        )

    elif any(x in msg for x in ["product", "dress", "shoe", "bag", "jewellery"]):
        return (
            "We sell:\n"
            "• Luxury Wears\n"
            "• Shoes\n"
            "• Bags\n"
            "• Jewellery & Accessories\n\n"
            "Please tell us which item you need."
        )

    elif any(x in msg for x in ["price", "cost"]):
        return (
            "Please tell us the product name and we'll provide the price."
        )

    elif any(x in msg for x in ["order", "buy"]):
        return (
            "To place an order, tell us:\n"
            "1. Product name\n"
            "2. Size\n"
            "3. Quantity\n"
            "4. Delivery location"
        )

    elif any(x in msg for x in ["delivery", "shipping"]):
        return (
            "Delivery is available across Nigeria.\n"
            "Please send us your city or state."
        )

    elif any(x in msg for x in ["payment", "transfer"]):
        return (
            "We accept bank transfer and WhatsApp payment confirmation."
        )

    elif any(x in msg for x in ["human", "agent", "representative", "call"]):
        return (
            f"Customer Service Phone: {PHONE_NUMBER}\n\n"
            "Click the WhatsApp button below to chat with us."
        )

    elif any(x in msg for x in ["thanks", "thank you"]):
        return (
            "You're welcome! ❤️ Thank you for shopping with RUTHELYN COLLECTIONS."
        )

    else:
        return (
            "Thank you for contacting RUTHELYN COLLECTIONS.\n"
            "Please explain your request in more detail."
        )


# ==========================================
# SEND MESSAGE
# ==========================================

def send_message(event=None):

    message = user_input.get().strip()

    if message == "":
        return

    chat_area.insert(tk.END, f"\nYou: {message}\n", "customer")

    response = get_response(message)

    chat_area.insert(
        tk.END,
        f"\n{BUSINESS_NAME}: {response}\n",
        "business"
    )

    current_time = datetime.now().strftime("%I:%M %p")

    chat_area.insert(
        tk.END,
        f"{current_time}\n",
        "time"
    )

    user_input.delete(0, tk.END)
    chat_area.see(tk.END)


# ==========================================
# CLEAR CHAT
# ==========================================

def clear_chat():
    chat_area.delete("1.0", tk.END)
    welcome_message()


def welcome_message():
    chat_area.insert(
        tk.END,
        f"Welcome to {BUSINESS_NAME} Customer Service!\n\n",
        "business"
    )

    chat_area.insert(
        tk.END,
        "You can ask about products, prices, orders, delivery, or payment.\n\n"
    )

    chat_area.insert(
        tk.END,
        f"Customer Service Phone: {PHONE_NUMBER}\n\n",
        "phone"
    )


# ==========================================
# WINDOW
# ==========================================

root = tk.Tk()
root.title(f"{BUSINESS_NAME} Customer Service")
root.geometry("700x750")
root.configure(bg="#F5F5F5")

# HEADER

header = tk.Frame(root, bg="#111111", height=100)
header.pack(fill=tk.X)

tk.Label(
    header,
    text=BUSINESS_NAME,
    bg="#111111",
    fg="white",
    font=("Arial", 22, "bold")
).pack(pady=(18, 5))

tk.Label(
    header,
    text="Luxury Wears • Shoes • Bags • Jewellery",
    bg="#111111",
    fg="#D4AF37",
    font=("Arial", 11)
).pack()

# CHAT

chat_area = scrolledtext.ScrolledText(
    root,
    wrap=tk.WORD,
    font=("Arial", 11)
)

chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

chat_area.tag_config("customer", foreground="#004AAD", font=("Arial", 11, "bold"))
chat_area.tag_config("business", foreground="#008060", font=("Arial", 11, "bold"))
chat_area.tag_config("phone", foreground="#B8860B", font=("Arial", 11, "bold"))
chat_area.tag_config("time", foreground="gray", font=("Arial", 8))

# INPUT

input_frame = tk.Frame(root, bg="#F5F5F5")
input_frame.pack(fill=tk.X, padx=10, pady=5)

user_input = tk.Entry(
    input_frame,
    font=("Arial", 12)
)

user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 10))

tk.Button(
    input_frame,
    text="Send",
    command=send_message,
    bg="#111111",
    fg="white",
    font=("Arial", 11, "bold"),
    width=10
).pack(side=tk.RIGHT)

# BUTTONS

button_frame = tk.Frame(root, bg="#F5F5F5")
button_frame.pack(fill=tk.X, padx=10, pady=10)

tk.Button(
    button_frame,
    text="💬 Chat on WhatsApp",
    command=open_whatsapp,
    bg="#25D366",
    fg="white",
    font=("Arial", 12, "bold"),
    pady=10
).pack(fill=tk.X)

tk.Button(
    button_frame,
    text="Clear Chat",
    command=clear_chat,
    bg="#DDDDDD",
    font=("Arial", 11),
    pady=8
).pack(fill=tk.X, pady=8)

# WELCOME MESSAGE

welcome_message()

root.bind("<Return>", send_message)

user_input.focus()

root.mainloop()

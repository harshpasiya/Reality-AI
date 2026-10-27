"""
Seed a demo broker user into the database and verify authentication.
"""
from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal
from app.models.broker import Broker
from app.models.customer import Customer
from app.core.security import hash_password, verify_password

db = SessionLocal()

try:
    # 1. Seed Demo Broker
    broker_email = "admin@reality.ai"
    broker_password = "adminpassword123"

    # Re-running resets the password instead of deleting the account, which
    # would fail once it owns listings, leads or conversations.
    broker = db.query(Broker).filter(Broker.email == broker_email).first()
    if broker is None:
        broker = Broker(name="Admin Broker", email=broker_email)
        db.add(broker)
    broker.password_hash = hash_password(broker_password)
    db.commit()
    db.refresh(broker)

    print("[OK] Demo broker ready:")
    print(f"   ID: {broker.id}")
    print(f"   Email: {broker.email}")
    print(f"   Password: {broker_password}")

    # 2. Seed Demo Customer
    customer_email = "customer@reality.ai"
    customer_password = "customerpassword123"

    # Re-running resets the password instead of deleting the account, which
    # would fail once it owns listings, leads or conversations.
    customer = db.query(Customer).filter(Customer.email == customer_email).first()
    if customer is None:
        customer = Customer(name="Demo Customer", email=customer_email)
        db.add(customer)
    customer.password_hash = hash_password(customer_password)
    db.commit()
    db.refresh(customer)

    print("[OK] Demo customer ready:")
    print(f"   ID: {customer.id}")
    print(f"   Email: {customer.email}")
    print(f"   Password: {customer_password}")

finally:
    db.close()

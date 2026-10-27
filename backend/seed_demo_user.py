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

    existing_broker = db.query(Broker).filter(Broker.email == broker_email).first()
    if existing_broker:
        db.delete(existing_broker)
        db.commit()

    broker = Broker(
        name="Admin Broker",
        email=broker_email,
        password_hash=hash_password(broker_password)
    )
    db.add(broker)
    db.commit()
    db.refresh(broker)

    print(f"✅ Demo Broker Created:")
    print(f"   ID: {broker.id}")
    print(f"   Email: {broker.email}")
    print(f"   Password: {broker_password}")

    # 2. Seed Demo Customer
    customer_email = "customer@reality.ai"
    customer_password = "customerpassword123"

    existing_customer = db.query(Customer).filter(Customer.email == customer_email).first()
    if existing_customer:
        db.delete(existing_customer)
        db.commit()

    customer = Customer(
        name="Demo Customer",
        email=customer_email,
        password_hash=hash_password(customer_password)
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    print(f"✅ Demo Customer Created:")
    print(f"   ID: {customer.id}")
    print(f"   Email: {customer.email}")
    print(f"   Password: {customer_password}")

finally:
    db.close()

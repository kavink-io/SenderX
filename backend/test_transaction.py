from app import create_app

app = create_app()

with app.app_context():
    db = app.mongo_db
    client = db.client

    try:
        with client.start_session() as session:
            session.start_transaction()

            db["_senderx_transaction_test"].insert_one(
                {"test": True},
                session=session
            )

            session.abort_transaction()

        print("MongoDB transactions: SUPPORTED")

    except Exception as error:
        print("MongoDB transactions: FAILED")
        print(type(error).__name__, str(error))
from mongoengine import connect


def register_test_db():
    connect(alias='default',
            host="mongodb://localhost/maintesoft_dev")
    connect(alias='test',
            host="mongodb://localhost/maintesoft_test")
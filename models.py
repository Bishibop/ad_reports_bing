from app import db

class Base(db.Model):

    __abstract__ = True

    id =                            db.Column(db.Integer, primary_key=True)
    created_at =                    db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at =                    db.Column(db.DateTime, default=db.func.current_timestamp(),
                                                          onupdate=db.func.current_timestamp())

class Customers(Base):
    name =                          db.Column(db.String)
    bing_ads_access_token =         db.Column(db.String)
    bing_ads_refresh_token =        db.Column(db.String)
    bing_ads_issued_at =            db.Column(db.DateTime)
    bing_ads_expires_in_seconds =   db.Column(db.Integer)


class Clients(Base):
    name =                          db.Column(db.String)
    bing_ads_aid =                  db.Column(db.String)
    customer_id =                   db.Column(db.Integer, db.ForeignKey('customers.id'))
    customer =                      db.relationship(Customers,
                                                    backref=db.backref('clients', lazy='dynamic'))

class BingadsReports(Base):
    cost =                          db.Column(db.Float)
    impressions =                   db.Column(db.Integer)
    click_through_rate =            db.Column(db.Float)
    clicks =                        db.Column(db.Integer)
    form_conversions =              db.Column(db.Integer)
    cost_per_conversion =           db.Column(db.Float)
    average_cost_per_click =        db.Column(db.Float)
    average_position =              db.Column(db.Float)
    conversion_rate =               db.Column(db.Float)
    date =                          db.Column(db.Date)
    client_id =                     db.Column(db.Integer, db.ForeignKey('clients.id'))
    client =                        db.relationship(Clients,
                                                    backref=db.backref('bingads_reports', lazy='dynamic'))

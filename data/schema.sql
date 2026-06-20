CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY,
  name        VARCHAR,
  email       VARCHAR,
  country     VARCHAR,
  created_at  DATE
);

CREATE TABLE products (
  product_id INTEGER PRIMARY KEY,
  name       VARCHAR,
  category   VARCHAR,
  price      DECIMAL(10,2)
);

CREATE TABLE orders (
  order_id    INTEGER PRIMARY KEY,
  customer_id INTEGER,
  order_date  DATE,
  status      VARCHAR
);

CREATE TABLE order_items (
  order_item_id INTEGER PRIMARY KEY,
  order_id      INTEGER,
  product_id    INTEGER,
  quantity      INTEGER,
  unit_price    DECIMAL(10,2)
);

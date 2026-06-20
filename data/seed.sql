INSERT INTO customers (customer_id, name, email, country, created_at) VALUES
  (1, 'Alice Johnson', 'alice@example.com', 'USA', DATE '2023-01-15'),
  (2, 'Bob Smith',     'bob@example.com',   'USA', DATE '2023-02-20'),
  (3, 'Carlos Diaz',   'carlos@example.com','Mexico', DATE '2023-03-10'),
  (4, 'Diana Prince',  'diana@example.com', 'UK', DATE '2023-04-05'),
  (5, 'Ethan Hunt',    'ethan@example.com', 'USA', DATE '2023-05-12'),
  (6, 'Fatima Noor',   'fatima@example.com','UAE', DATE '2023-06-18'),
  (7, 'Grace Lee',     'grace@example.com', 'Canada', DATE '2023-07-22'),
  (8, 'Hiro Tanaka',   'hiro@example.com',  'Japan', DATE '2023-08-30');

INSERT INTO products (product_id, name, category, price) VALUES
  (1,  'Laptop',        'Electronics', 1200.00),
  (2,  'Smartphone',    'Electronics', 800.00),
  (3,  'Headphones',    'Electronics', 150.00),
  (4,  'Desk Chair',    'Furniture',   250.00),
  (5,  'Standing Desk', 'Furniture',   450.00),
  (6,  'Coffee Maker',  'Appliances',  90.00),
  (7,  'Blender',       'Appliances',  60.00),
  (8,  'Notebook',      'Stationery',  5.00),
  (9,  'Pen Set',       'Stationery',  12.00),
  (10, 'Monitor',       'Electronics', 300.00);

INSERT INTO orders (order_id, customer_id, order_date, status) VALUES
  (1,  1, DATE '2023-09-01', 'completed'),
  (2,  2, DATE '2023-09-03', 'completed'),
  (3,  1, DATE '2023-09-10', 'completed'),
  (4,  3, DATE '2023-09-15', 'shipped'),
  (5,  4, DATE '2023-10-01', 'completed'),
  (6,  5, DATE '2023-10-05', 'cancelled'),
  (7,  2, DATE '2023-10-10', 'completed'),
  (8,  6, DATE '2023-10-12', 'shipped'),
  (9,  7, DATE '2023-11-01', 'completed'),
  (10, 1, DATE '2023-11-05', 'completed'),
  (11, 8, DATE '2023-11-20', 'pending'),
  (12, 5, DATE '2023-12-01', 'completed');

INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES
  (1,  1,  1,  1, 1200.00),
  (2,  1,  3,  2, 150.00),
  (3,  2,  2,  1, 800.00),
  (4,  3,  10, 2, 300.00),
  (5,  3,  8,  5, 5.00),
  (6,  4,  4,  1, 250.00),
  (7,  5,  5,  1, 450.00),
  (8,  5,  4,  2, 250.00),
  (9,  6,  2,  1, 800.00),
  (10, 7,  6,  1, 90.00),
  (11, 7,  7,  1, 60.00),
  (12, 8,  1,  1, 1200.00),
  (13, 9,  3,  1, 150.00),
  (14, 9,  9,  3, 12.00),
  (15, 10, 2,  1, 800.00),
  (16, 11, 8,  10, 5.00),
  (17, 12, 10, 1, 300.00);

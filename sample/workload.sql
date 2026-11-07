-- Frequencies are supplied separately; literals are representative examples.
SELECT id, created_at, total FROM public.orders
WHERE user_id = 101 AND created_at >= TIMESTAMPTZ '2025-06-01 UTC'
ORDER BY created_at DESC;

SELECT id, user_id, total FROM public.orders
WHERE status = 'pending' AND created_at >= TIMESTAMPTZ '2025-11-01 UTC';

SELECT p.category, sum(i.quantity * i.unit_price) AS revenue
FROM public.order_items AS i
JOIN public.products AS p ON p.id = i.product_id
WHERE p.category = 'category-3'
GROUP BY p.category;

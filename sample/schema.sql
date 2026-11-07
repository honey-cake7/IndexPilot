CREATE TABLE IF NOT EXISTS public.users (
    id bigint PRIMARY KEY,
    email text NOT NULL UNIQUE,
    region text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.products (
    id bigint PRIMARY KEY,
    category text NOT NULL,
    price numeric(12,2) NOT NULL CHECK (price > 0)
);
CREATE TABLE IF NOT EXISTS public.orders (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(id),
    created_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled')),
    total numeric(14,2) NOT NULL CHECK (total > 0)
);
CREATE TABLE IF NOT EXISTS public.order_items (
    order_id bigint NOT NULL REFERENCES public.orders(id),
    line_number smallint NOT NULL,
    product_id bigint NOT NULL REFERENCES public.products(id),
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(12,2) NOT NULL CHECK (unit_price > 0),
    PRIMARY KEY (order_id, line_number)
);
CREATE TABLE IF NOT EXISTS public.payments (
    id bigint PRIMARY KEY,
    order_id bigint NOT NULL UNIQUE REFERENCES public.orders(id),
    amount numeric(14,2) NOT NULL CHECK (amount > 0),
    status text NOT NULL CHECK (status IN ('captured', 'failed'))
);
CREATE TABLE IF NOT EXISTS public.indexpilot_dataset (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    seed integer NOT NULL,
    order_count integer NOT NULL CHECK (order_count > 0),
    anchor timestamptz NOT NULL,
    generator_version integer NOT NULL
);

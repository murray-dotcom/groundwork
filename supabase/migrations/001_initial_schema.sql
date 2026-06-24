-- Groundwork Property Intelligence Database
-- Initial schema for Home Ground Real Estate

create table transactions (
    id                  uuid        primary key default gen_random_uuid(),
    title_deed_no       text        not null,
    estate              text        not null,
    township            text,
    erf                 integer,
    portion             integer     default 0,
    sectional_scheme    text,                           -- normalised, uppercase, trimmed
    unit                text,
    suburb              text,
    street              text,
    street_number       text,
    sales_date          date,
    registration_date   date        not null,
    sales_price         bigint,
    size_m2             integer,
    price_per_m2        integer,
    possible_land_only  boolean     default false,
    buyer_type          text        check (buyer_type in ('natural_person', 'legal_entity')),
    seller_type         text        check (seller_type in ('natural_person', 'legal_entity')),
    number_of_owners    integer,
    property_type       text        check (property_type in ('sectional_title', 'freehold')),
    is_market_sale      boolean,
    data_source         text        default 'lightstone_export',
    imported_at         timestamptz default now()
);

-- Composite natural key used for upserts
create unique index transactions_natural_key on transactions (title_deed_no, coalesce(unit, ''));

create index idx_transactions_estate_reg_date
    on transactions (estate, registration_date);

create index idx_transactions_estate_type_reg_date
    on transactions (estate, property_type, registration_date);

create index idx_transactions_scheme_reg_date
    on transactions (sectional_scheme, registration_date);

create index idx_transactions_street_reg_date
    on transactions (street, registration_date);

create index idx_transactions_market_sale_estate_reg_date
    on transactions (is_market_sale, estate, registration_date);


create table import_log (
    id                  uuid        primary key default gen_random_uuid(),
    filename            text,
    estate              text,
    records_raw         integer,
    records_imported    integer,
    records_excluded    integer,
    exclusion_summary   jsonb,
    imported_at         timestamptz default now()
);

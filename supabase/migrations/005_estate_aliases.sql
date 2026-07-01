CREATE TABLE estate_aliases (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_estate text        NOT NULL,
  alias            text        NOT NULL,
  source           text        CHECK (source IN (
                                 'property24', 'private_property', 'manual'
                               )),
  created_at       timestamptz DEFAULT now(),
  UNIQUE (alias, source)
);

CREATE INDEX idx_estate_aliases_alias
  ON estate_aliases (alias);
CREATE INDEX idx_estate_aliases_canonical
  ON estate_aliases (canonical_estate);

ALTER TABLE estate_aliases ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read estate_aliases"
  ON estate_aliases FOR SELECT USING (true);

CREATE POLICY "public insert estate_aliases"
  ON estate_aliases FOR INSERT WITH CHECK (true);

-- Seed known aliases
INSERT INTO estate_aliases (canonical_estate, alias, source) VALUES
  ('Elaleni Coastal Estate',          'Elaleni Coastal Estate',          'property24'),
  ('Elaleni Coastal Estate',          'Elaleni Coastal Forest Estate',    'property24'),
  ('Elaleni Coastal Estate',          'Elaleni Lifestyle Estate',         'property24'),
  ('Elaleni Coastal Estate',          'Elaleni Coastal Estate',          'private_property'),
  ('Elaleni Coastal Estate',          'Elaleni Coastal Forest Estate',    'private_property'),
  ('Elaleni Coastal Estate',          'Elaleni Lifestyle Estate',         'private_property'),
  ('Simbithi Eco Estate',             'Simbithi Eco Estate',             'property24'),
  ('Simbithi Eco Estate',             'Simbithi Eco-Estate',             'property24'),
  ('Simbithi Eco Estate',             'Simbithi',                        'property24'),
  ('Dunkirk Estate',                  'Dunkirk Estate',                  'property24'),
  ('Dunkirk Estate',                  'Dunkirk',                         'property24'),
  ('Brettenwood Coastal Estate',      'Brettenwood Coastal Estate',      'property24'),
  ('Brettenwood Coastal Estate',      'Brettenwood',                     'property24'),
  ('Zululami Luxury Coastal Estate',  'Zululami Luxury Coastal Estate',  'property24'),
  ('Zululami Luxury Coastal Estate',  'Zululami',                        'property24'),
  ('Zululami Luxury Coastal Estate',  'Zululami Coastal Estate',         'property24');

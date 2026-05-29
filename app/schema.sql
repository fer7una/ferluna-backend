CREATE TABLE IF NOT EXISTS site_profile (
    id TEXT PRIMARY KEY DEFAULT 'profile' CHECK (id = 'profile'),
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    tagline TEXT NOT NULL,
    location TEXT NOT NULL,
    email TEXT NOT NULL,
    avatar_alt TEXT NOT NULL,
    highlights TEXT[] NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profile_links (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    href TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('github', 'linkedin', 'mail', 'web')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS site_sections (
    id TEXT PRIMARY KEY,
    route TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    eyebrow TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    icon_key TEXT NOT NULL,
    orbit TEXT NOT NULL CHECK (orbit IN ('inner', 'outer')),
    angle DOUBLE PRECISION NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    visible_from TIMESTAMPTZ,
    visible_until TIMESTAMPTZ,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS section_items (
    id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL REFERENCES site_sections(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    kicker TEXT NOT NULL,
    title TEXT NOT NULL,
    meta TEXT,
    description TEXT NOT NULL,
    href TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    icon_key TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    visible_from TIMESTAMPTZ,
    visible_until TIMESTAMPTZ,
    featured BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS momentary_tabs (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    icon_key TEXT NOT NULL,
    angle DOUBLE PRECISION NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    visible_from TIMESTAMPTZ,
    visible_until TIMESTAMPTZ,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS momentary_items (
    id TEXT PRIMARY KEY,
    tab_id TEXT NOT NULL REFERENCES momentary_tabs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    kicker TEXT NOT NULL,
    title TEXT NOT NULL,
    meta TEXT,
    description TEXT NOT NULL,
    href TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    icon_key TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    visible_from TIMESTAMPTZ,
    visible_until TIMESTAMPTZ,
    featured BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS site_revision (
    id TEXT PRIMARY KEY DEFAULT 'revision' CHECK (id = 'revision'),
    revision BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_site_sections_public
    ON site_sections (enabled, sort_order);

CREATE INDEX IF NOT EXISTS idx_section_items_section_order
    ON section_items (section_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_momentary_tabs_public
    ON momentary_tabs (enabled, sort_order);

CREATE INDEX IF NOT EXISTS idx_momentary_items_tab_order
    ON momentary_items (tab_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_profile_links_order
    ON profile_links (sort_order);

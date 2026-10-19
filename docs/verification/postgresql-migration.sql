BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> e66d6a547325

CREATE TABLE cleanup_outbox (
    id VARCHAR(36) NOT NULL, 
    paper_id VARCHAR(36) NOT NULL, 
    done BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (paper_id)
);

CREATE TABLE users (
    id VARCHAR(36) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    password_hash TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE libraries (
    id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_libraries_owner_id ON libraries (owner_id);

CREATE TABLE conversations (
    id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    library_id VARCHAR(36) NOT NULL, 
    title TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(library_id) REFERENCES libraries (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_conversations_library_id ON conversations (library_id);

CREATE INDEX ix_conversations_owner_id ON conversations (owner_id);

CREATE TABLE evaluation_runs (
    id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    library_id VARCHAR(36) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    result JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(library_id) REFERENCES libraries (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_evaluation_runs_owner_id ON evaluation_runs (owner_id);

CREATE TABLE papers (
    id VARCHAR(36) NOT NULL, 
    library_id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    title TEXT NOT NULL, 
    filename VARCHAR(255) NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    error TEXT, 
    metadata_json JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(library_id) REFERENCES libraries (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id), 
    UNIQUE (library_id, sha256)
);

CREATE INDEX ix_papers_library_id ON papers (library_id);

CREATE INDEX ix_papers_owner_id ON papers (owner_id);

CREATE TABLE evidence (
    id VARCHAR(36) NOT NULL, 
    paper_id VARCHAR(36) NOT NULL, 
    library_id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    section TEXT, 
    page INTEGER, 
    text TEXT NOT NULL, 
    locator JSON NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(library_id) REFERENCES libraries (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id), 
    FOREIGN KEY(paper_id) REFERENCES papers (id)
);

CREATE INDEX ix_evidence_library_id ON evidence (library_id);

CREATE INDEX ix_evidence_owner_id ON evidence (owner_id);

CREATE INDEX ix_evidence_paper_id ON evidence (paper_id);

CREATE TABLE experiments (
    id VARCHAR(36) NOT NULL, 
    paper_id VARCHAR(36) NOT NULL, 
    library_id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    model_name VARCHAR(200), 
    dataset_name VARCHAR(200), 
    metric_name VARCHAR(100), 
    record JSON NOT NULL, 
    original_record JSON NOT NULL, 
    version INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(library_id) REFERENCES libraries (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id), 
    FOREIGN KEY(paper_id) REFERENCES papers (id), 
    UNIQUE (paper_id, fingerprint)
);

CREATE INDEX ix_experiment_lookup ON experiments (owner_id, model_name, dataset_name);

CREATE INDEX ix_experiments_dataset_name ON experiments (dataset_name);

CREATE INDEX ix_experiments_library_id ON experiments (library_id);

CREATE INDEX ix_experiments_metric_name ON experiments (metric_name);

CREATE INDEX ix_experiments_model_name ON experiments (model_name);

CREATE INDEX ix_experiments_owner_id ON experiments (owner_id);

CREATE INDEX ix_experiments_paper_id ON experiments (paper_id);

CREATE TABLE extraction_jobs (
    id VARCHAR(36) NOT NULL, 
    paper_id VARCHAR(36) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    stage VARCHAR(40) NOT NULL, 
    details JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(paper_id) REFERENCES papers (id)
);

CREATE INDEX ix_extraction_jobs_paper_id ON extraction_jobs (paper_id);

CREATE TABLE messages (
    id VARCHAR(36) NOT NULL, 
    conversation_id VARCHAR(36) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    content TEXT NOT NULL, 
    details JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id)
);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

CREATE TABLE extraction_revisions (
    id VARCHAR(36) NOT NULL, 
    experiment_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    before JSON NOT NULL, 
    after JSON NOT NULL, 
    reason TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(experiment_id) REFERENCES experiments (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_extraction_revisions_experiment_id ON extraction_revisions (experiment_id);

INSERT INTO alembic_version (version_num) VALUES ('e66d6a547325') RETURNING alembic_version.version_num;

-- Running upgrade e66d6a547325 -> a2ed23925b49

ALTER TABLE extraction_jobs ADD COLUMN started_at TIMESTAMP WITH TIME ZONE;

UPDATE alembic_version SET version_num='a2ed23925b49' WHERE alembic_version.version_num = 'e66d6a547325';

-- Running upgrade a2ed23925b49 -> ae5fbc09260d

CREATE TABLE public_references (
    id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(36) NOT NULL, 
    library_id VARCHAR(36) NOT NULL, 
    external_id VARCHAR(100) NOT NULL, 
    metadata_json JSON NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(library_id) REFERENCES libraries (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id), 
    UNIQUE (library_id, external_id)
);

CREATE INDEX ix_public_references_library_id ON public_references (library_id);

CREATE INDEX ix_public_references_owner_id ON public_references (owner_id);

UPDATE alembic_version SET version_num='ae5fbc09260d' WHERE alembic_version.version_num = 'a2ed23925b49';

-- Running upgrade ae5fbc09260d -> 63fa391b4bb1

ALTER TABLE papers ADD COLUMN extraction_lock VARCHAR(36);

UPDATE alembic_version SET version_num='63fa391b4bb1' WHERE alembic_version.version_num = 'ae5fbc09260d';

COMMIT;


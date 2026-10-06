-- A credential per robot agent.
--
-- Until now an agent was recognised by *not* being signed in: anything that
-- could reach the API without a cookie was treated as a robot, and could switch
-- a robot's mode, reassign its map, publish maps and rewrite runs. Each robot
-- now gets its own bearer token, minted by an admin and shown once.
--
-- Only the SHA-256 of the token is stored (see security.hash_token): the token
-- is 256 random bits, so there is nothing to guess and no need for a slow hash,
-- and a copy of the database is not a copy of every robot's credential.
--
-- A token binds its caller to one robot. An agent holding robot A's token may
-- not change robot B, which is enforced by the API rather than by convention.
--
-- SQLite cannot add a UNIQUE column with ALTER TABLE, so uniqueness is a
-- separate index. NULL (no token yet) is allowed on any number of rows.

ALTER TABLE robots ADD COLUMN agent_token_hash TEXT;
ALTER TABLE robots ADD COLUMN agent_token_created_at TEXT;

CREATE UNIQUE INDEX robots_agent_token_hash_unique ON robots (agent_token_hash);

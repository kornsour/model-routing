# ADR-0003: Version the JSON API in the path

Status: Accepted

Field names are part of the contract with the sites. Breaking changes ship
under a new `/vN/` prefix; `/v1/` stays until every site has moved.

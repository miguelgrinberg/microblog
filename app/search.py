from app import state


def add_to_index(index, model):
    if not state.elasticsearch:
        return
    payload = {field: getattr(model, field) for field in model.__searchable__}
    state.elasticsearch.index(index=index, id=model.id, document=payload)


def remove_from_index(index, model):
    if not state.elasticsearch:
        return
    state.elasticsearch.delete(index=index, id=model.id)


def query_index(index, query, page, per_page):
    if not state.elasticsearch:
        return [], 0
    search = state.elasticsearch.search(
        index=index,
        query={'multi_match': {'query': query, 'fields': ['*']}},
        from_=(page - 1) * per_page,
        size=per_page)
    ids = [int(hit['_id']) for hit in search['hits']['hits']]
    return ids, search['hits']['total']['value']

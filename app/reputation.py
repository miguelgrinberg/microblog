"""ЛР6, Завд.3: той самий метод через таблицю пошуку (CC = 1)."""

_BADGES = {
    ('admin', 1): 'gold', ('admin', 2): 'silver',
    ('moderator', 1): 'silver', ('moderator', 2): 'bronze',
    ('member', 1): 'bronze', ('member', 2): 'basic',
    ('guest', 1): 'basic',
}


def reputation_badge(role, level):
    return _BADGES.get((role, level), 'none')

# SCA: початковий звіт (pip-audit 2.10.1)

Команда: `pip-audit -r requirements.txt` (вихідний `requirements.txt` з коміту 1603c9c)

Результат: **94 записи pip-audit** = **54 унікальних advisories** у 17 з 54 компонентів (записи PYSEC і GHSA/CVE описують ті самі вразливості).

Критичність і CVSS за GitHub Advisory Database (pip-audit severity не повертає). Тип залежності визначено за деревом `pipdeptree` і імпортами коду: пряма = імпортується в коді проєкту або не є залежністю жодного іншого пакета.

| Severity | Кількість |
|---|---|
| Critical | 1 |
| High | 14 |
| Medium | 29 |
| Low | 4 |
| не вдалося отримати (сторінка advisory недоступна) | 6 |

| Компонент | Встановлена | Виправлена | Тип | Advisory | CVE | Severity | CVSS | Рішення |
|---|---|---|---|---|---|---|---|---|
| pyjwt | 2.8.0 | 2.14.0 | пряма | GHSA-ffc3-869f-jxw9 | CVE-2026-102268 | Critical | 9.1 | оновити |
| gunicorn | 21.2.0 | 22.0.0 | пряма | GHSA-w3h3-4rj7-4ph4 | CVE-2024-1135 | High | 8.2 | оновити |
| gunicorn | 21.2.0 | 22.0.0 | пряма | GHSA-hc5x-x2vx-497g | CVE-2024-6827 | High | 7.5 | оновити |
| httpie | 3.2.2 | 3.2.3 | пряма | GHSA-8r96-8889-qg2x | CVE-2023-48052 | High | 7.4 | оновити |
| mako | 1.3.0 | 1.3.12 | транзитивна (через alembic) | GHSA-2h4p-vjrc-8xpq | CVE-2026-44307 | High | 8.7 | оновити |
| pyjwt | 2.8.0 | 2.12.0 | пряма | GHSA-752w-5fwx-jx9f | CVE-2026-32597 | High | 7.5 | оновити |
| pyjwt | 2.8.0 | 2.13.0 | пряма | GHSA-xgmm-8j9v-c9wx | CVE-2026-48526 | High | 7.4 | оновити |
| setuptools | 68.2.2 | 78.1.1 | транзитивна (через httpie) | GHSA-5rjg-fvgr-3xxf | CVE-2025-47273 | High | 7.7 | оновити |
| setuptools | 68.2.2 | 70.0.0 | транзитивна (через httpie) | GHSA-cx63-2mw6-8hw5 | CVE-2024-6345 | High | 7.5 | оновити |
| urllib3 | 2.1.0 | 2.6.0 | транзитивна (через requests, elastic-transport) | GHSA-gm62-xv2j-4w53 | CVE-2025-66418 | High | 8.9 | оновити |
| urllib3 | 2.1.0 | 2.6.0 | транзитивна (через requests, elastic-transport) | GHSA-2xpw-w6gg-jr37 | CVE-2025-66471 | High | 8.9 | оновити |
| urllib3 | 2.1.0 | 2.6.3 | транзитивна (через requests, elastic-transport) | GHSA-38jv-5279-wg99 | CVE-2026-21441 | High | 8.9 | оновити |
| urllib3 | 2.1.0 | 2.7.0 | транзитивна (через requests, elastic-transport) | GHSA-qccp-gfcp-xxvc | CVE-2026-44431 | High | 8.2 | оновити |
| urllib3 | 2.1.0 | 2.8.0 | транзитивна (через requests, elastic-transport) | GHSA-vxq7-64xx-v4gw | CVE-2026-97689 | High | 8.9 | оновити |
| werkzeug | 3.0.1 | 3.0.3 | пряма (імпорт у коді) і через flask | GHSA-2g68-c3qc-8985 | CVE-2024-34069 | High | 7.5 | оновити |
| aiosmtpd | 1.4.4.post2 | 1.4.5 | пряма | GHSA-pr2m-px7j-xg65 | CVE-2024-27305 | Medium | — | оновити |
| aiosmtpd | 1.4.4.post2 | 1.4.6 | пряма | GHSA-wgjv-9j3q-jhg8 | CVE-2024-34083 | Medium | — | оновити |
| dnspython | 2.4.2 | 2.6.1 | транзитивна (через email-validator) | GHSA-3rq5-2g8h-59hc | CVE-2023-29483 | Medium | — | оновити |
| flask-httpauth | 4.8.0 | 4.8.1 | пряма | GHSA-p44q-vqpr-4xmg | CVE-2026-34531 | Medium | — | оновити |
| idna | 3.4 | 3.7 | транзитивна (через requests, email-validator) | GHSA-jjg7-2v4v-x38h | CVE-2024-3651 | Medium | — | оновити |
| idna | 3.4 | 3.15 | транзитивна (через requests, email-validator) | GHSA-65pc-fj4g-8rjx | CVE-2026-45409 | Medium | — | оновити |
| jinja2 | 3.1.2 | 3.1.3 | транзитивна (через flask, flask-babel) | GHSA-h5c8-rqwp-cp95 | CVE-2024-22195 | Medium | — | оновити |
| jinja2 | 3.1.2 | 3.1.4 | транзитивна (через flask, flask-babel) | GHSA-h75v-3vvj-5mfj | CVE-2024-34064 | Medium | — | оновити |
| jinja2 | 3.1.2 | 3.1.5 | транзитивна (через flask, flask-babel) | GHSA-q2x7-8rv6-6q7h | CVE-2024-56326 | Medium | — | оновити |
| jinja2 | 3.1.2 | 3.1.5 | транзитивна (через flask, flask-babel) | GHSA-gmj6-6f8f-6699 | CVE-2024-56201 | Medium | — | оновити |
| jinja2 | 3.1.2 | 3.1.6 | транзитивна (через flask, flask-babel) | GHSA-cpwx-vrp4-4pq7 | CVE-2025-27516 | Medium | — | оновити |
| pyjwt | 2.8.0 | 2.13.0 | пряма | GHSA-993g-76c3-p5m4 | CVE-2026-48522 | Medium | — | оновити |
| pyjwt | 2.8.0 | 2.13.0 | пряма | GHSA-w7vc-732c-9m39 | CVE-2026-48525 | Medium | — | оновити |
| pyjwt | 2.8.0 | 2.14.0 | пряма | GHSA-jwrc-g2q2-pq5p | CVE-2026-102270 | Medium | — | оновити |
| pyjwt | 2.8.0 | 2.14.0 | пряма | GHSA-2gx3-rcp4-g85q | CVE-2026-101917 | Medium | 5.3 | оновити |
| pyjwt | 2.8.0 | 2.15.0 | пряма | GHSA-42vr-xj54-vc7v | CVE-2026-101918 | Medium | — | оновити |
| pyjwt | 2.8.0 | 2.14.0 | пряма | GHSA-hxm8-2xgr-2p9m | CVE-2026-102269 | Medium | — | оновити |
| python-dotenv | 1.0.0 | 1.2.2 | пряма | GHSA-mf9w-mj56-hr94 | CVE-2026-28684 | Medium | — | оновити |
| requests | 2.31.0 | 2.32.0 | пряма (імпорт у коді) і через httpie | GHSA-9wx4-h78v-vm56 | CVE-2024-35195 | Medium | — | оновити |
| requests | 2.31.0 | 2.32.4 | пряма (імпорт у коді) і через httpie | GHSA-9hjg-9r4m-mvj7 | CVE-2024-47081 | Medium | — | оновити |
| requests | 2.31.0 | 2.33.0 | пряма (імпорт у коді) і через httpie | GHSA-gc5v-m9x4-r6x2 | CVE-2026-25645 | Medium | — | оновити |
| setuptools | 68.2.2 | 83.0.0 | транзитивна (через httpie) | GHSA-h35f-9h28-mq5c | CVE-2026-59890 | Medium | — | оновити |
| urllib3 | 2.1.0 | 1.26.19, 2.2.2 | транзитивна (через requests, elastic-transport) | GHSA-34jh-p97f-mpxf | CVE-2024-37891 | Medium | — | оновити |
| urllib3 | 2.1.0 | 2.5.0 | транзитивна (через requests, elastic-transport) | GHSA-pq67-6m6q-mj2v | CVE-2025-50181 | Medium | — | оновити |
| werkzeug | 3.0.1 | 3.0.6 | пряма (імпорт у коді) і через flask | GHSA-f9vj-2wh5-fj8j | CVE-2024-49766 | Medium | — | оновити |
| werkzeug | 3.0.1 | 3.0.6 | пряма (імпорт у коді) і через flask | GHSA-q34m-jh98-gwm2 | CVE-2024-49767 | Medium | — | оновити |
| werkzeug | 3.0.1 | 3.1.4 | пряма (імпорт у коді) і через flask | GHSA-hgf8-39gv-g3f2 | CVE-2025-66221 | Medium | — | оновити |
| werkzeug | 3.0.1 | 3.1.5 | пряма (імпорт у коді) і через flask | GHSA-87hc-h4r5-73f7 | CVE-2026-21860 | Medium | — | оновити |
| werkzeug | 3.0.1 | 3.1.6 | пряма (імпорт у коді) і через flask | GHSA-29vq-49wr-vm6x | CVE-2026-27199 | Medium | — | оновити |
| certifi | 2023.11.17 | 2024.7.4 | транзитивна (через requests, elastic-transport) | GHSA-248v-346w-9cwc | CVE-2024-39689 | Low | — | оновити |
| flask | 3.0.0 | 3.1.3 | пряма | GHSA-68rp-wp8r-4726 | CVE-2026-27205 | Low | — | оновити |
| pygments | 2.17.1 | 2.20.0 | транзитивна (через httpie, rich) | GHSA-5239-wwwm-4pmq | CVE-2026-4539 | Low | — | оновити |
| pyjwt | 2.8.0 | 2.13.0 | пряма | GHSA-fhv5-28vv-h8m8 | CVE-2026-48524 | Low | — | оновити |
| pyjwt | 2.8.0 | — | пряма | PYSEC-2025-183 | CVE-2025-45768 | н/д | — | оновити |
| pyjwt | 2.8.0 | 2.14.0 | пряма | GHSA-p4g4-x82p-q773 | CVE-2026-102271 | н/д | — | оновити |
| pyjwt | 2.8.0 | 2.14.0 | пряма | GHSA-9v7f-9g4p-ffgj | CVE-2026-102267 | н/д | — | оновити |
| pyjwt | 2.8.0 | 2.15.0 | пряма | GHSA-x33g-cr3x-6449 | CVE-2026-102275 | н/д | — | оновити |
| urllib3 | 2.1.0 | 2.8.0 | транзитивна (через requests, elastic-transport) | GHSA-8988-9cw3-xx77 | CVE-2026-97687 | н/д | — | оновити |
| werkzeug | 3.0.1 | 3.1.9 | пряма (імпорт у коді) і через flask | GHSA-g6x2-hccm-hh4m | — | н/д | — | оновити |

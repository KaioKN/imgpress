# imgpress — Operations Runbook

Эксплуатационная памятка по сайту imgpress, развёрнутому на личном VPS.
Рассчитана на то, чтобы любой оператор (человек или ИИ-агент) мог управлять
сервисом, ничего не сломав в соседнем VPN.

## TL;DR
- **Сайт:** http://45.136.228.178:8081 (HTTP, без HTTPS — осознанно).
- **Сервер:** `ssh root@45.136.228.178` (Debian 12, ~1.9 ГБ RAM).
- **Код на сервере:** `/opt/imgpress` (venv в `/opt/imgpress/.venv`).
- **Сервис:** systemd-юнит `imgpress.service`, gunicorn на `0.0.0.0:8081`.
- **GitHub:** `git@github.com:KaioKN/imgpress.git` (ветка `main`).
- **Исходники локально:** `~/Desktop/claude/projects/web/imgpress`.

## ⚠️ Этот сервер — ОДНОВРЕМЕННО VPN. Не трогать!
На той же машине крутится личный VPN. Любое из этого ломать/занимать нельзя:

| Порт | Протокол | Сервис | Назначение |
|---|---|---|---|
| 8081 | TCP | gunicorn (imgpress) | **наш сайт — им и управляем** |
| 443 | TCP | Xray (VLESS+REALITY) | VPN — НЕ ТРОГАТЬ |
| 64195 | UDP | WireGuard (wg0) | VPN — НЕ ТРОГАТЬ |
| 33573 | TCP | 3x-ui панель (x-ui) | управление VPN — НЕ ТРОГАТЬ |

Внутренний VPN-IP сервера: `10.66.66.1` (роутер-пир — `10.66.66.2`).
**Запрещено:** ставить nginx/Caddy на 80/443, выпускать сертификаты, менять
фаервол так, чтобы задеть UDP 64195 / TCP 443 / 33573, трогать `/etc/wireguard/*`
и конфиг Xray. Сайт живёт на отдельном порту именно чтобы не конфликтовать с VPN.

## Управление сервисом
```bash
systemctl status imgpress         # состояние
systemctl restart imgpress        # перезапуск
systemctl stop imgpress           # остановить
systemctl start imgpress          # запустить
journalctl -u imgpress -n 50 -f   # логи (live)
```

## Обновление кода (деплой новой версии)
Код едет напрямую из локального git (на сервере нет rsync; GitHub — отдельно).
```bash
cd ~/Desktop/claude/projects/web/imgpress
# 1) запушить в GitHub (по SSH-ключу)
git push
# 2) доставить на сервер
git archive --format=tar main | ssh root@45.136.228.178 'tar -x -C /opt/imgpress'
# 3) если менялись зависимости:
ssh root@45.136.228.178 '/opt/imgpress/.venv/bin/pip install -r /opt/imgpress/requirements.txt'
# 4) перезапустить
ssh root@45.136.228.178 'systemctl restart imgpress'
```

## Защита от OOM (почему VPN в безопасности)
Юнит `/etc/systemd/system/imgpress.service` содержит:
- `MemoryMax=512M` — жёсткий потолок памяти; превысит — ядро убьёт **imgpress**.
- `OOMScoreAdjust=500` — при общей нехватке RAM жертвой выбирается imgpress, не VPN.
- `WEB_WORKERS=2` — мало воркеров под малую RAM.

Если на легитимных больших картинках сервис стало убивать по памяти — поднять
лимит: в юните `MemoryMax=768M`, затем `systemctl daemon-reload && systemctl restart imgpress`.

## Диагностика
```bash
# сайт отвечает локально?
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/
# слушает порт?
ss -tlnp | grep :8081
# сколько памяти ест сейчас?
systemctl show imgpress -p MemoryCurrent --value
# VPN цел? (должны быть оба)
ss -tlnp | grep :443        # xray
wg show                      # wireguard, listening port 64195
```
Если снаружи (`http://45.136.228.178:8081`) не открывается, а локально 200 —
порт прикрыт edge-фаерволом хостинга (AEZA): открыть 8081/TCP в панели провайдера.

## Полный откат (убрать сайт, VPN не трогается)
```bash
ssh root@45.136.228.178 '
  systemctl disable --now imgpress &&
  rm /etc/systemd/system/imgpress.service &&
  systemctl daemon-reload &&
  rm -rf /opt/imgpress'
```

## Известные ограничения
- **Только HTTP**, без HTTPS (443 занят VPN). Браузер покажет «не защищено».
- Домен `arthas.online` сюда НЕ направлен. Для домена+HTTPS — PaaS (Render,
  `render.yaml` в репо) или отдельный сервер, а не борьба с Xray за 443.
- Бесплатного «засыпания» нет — это свой сервер, работает постоянно.

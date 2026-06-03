# SNIN Mesh Fabric — Репозитории

## ⚡ РАБОЧИЙ КОД (живая инфраструктура)
**Путь:** `/home/agent/data/sites/relay-mesh/`
**Git в этой папке:** служебный, НЕ для коммитов
**Что тут делать:** писать код, править файлы, запускать тесты

## 📦 GIT-ИСТОРИЯ (куда коммитить)
**Путь:** `/home/agent/data/projects/snin-v5-mesh-fabric/`
**Что тут делать:** копировать сюда изменённые файлы из relay-mesh → git add → git commit

## Алгоритм
1. Правим файлы в `/home/agent/data/sites/relay-mesh/`
2. Копируем изменённые файлы: `cp -r /home/agent/data/sites/relay-mesh/{file} /home/agent/data/projects/snin-v5-mesh-fabric/{file}`
3. `cd /home/agent/data/projects/snin-v5-mesh-fabric && git add . && git commit -m "..."`

## Почему так
- relay-mesh — развёрнутая инфраструктура, supervisor смотрит сюда
- project — чистая git-история без логов, БД и служебных файлов

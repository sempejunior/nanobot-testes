.PHONY: up down dev build rebuild logs shell

# Start the application in production mode (using the built image)
up:
	docker compose up -d

# Stop and remove all containers
down:
	docker compose down

# Rebuild the Docker image
build:
	docker compose build

# Rebuild and start in production mode
rebuild:
	docker compose up -d --build

# Start the application in development mode with hot-reload
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo ""
	@echo "  ┌─────────────────────────────────────────────────┐"
	@echo "  │  Dev mode ready!                                │"
	@echo "  │                                                 │"
	@echo "  │  Frontend:  http://localhost:5173                │"
	@echo "  │  API:       http://localhost:18790               │"
	@echo "  │  noVNC:     http://localhost:6080/vnc.html       │"
	@echo "  │                                                 │"
	@echo "  │  Frontend has hot-reload via Vite.              │"
	@echo "  │  Python code has hot-reload via watchmedo.      │"
	@echo "  └─────────────────────────────────────────────────┘"
	@echo ""
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Follow the container logs
logs:
	docker compose logs -f nanobot-gateway

# Access the container shell
shell:
	docker exec -it nanobot-gateway /bin/bash

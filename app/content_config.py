from __future__ import annotations

from app.data import CV, DOCS, POSTS, PROJECTS

SECTIONS = [
    {
        "id": "cv",
        "route": "cv",
        "label": "CV",
        "eyebrow": "Trayectoria",
        "title": "CV vivo",
        "description": "Experiencia, capacidades y foco profesional.",
        "iconKey": "briefcase",
        "orbit": "inner",
        "angle": -90,
        "order": 10,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
    {
        "id": "projects",
        "route": "projects",
        "label": "Proyectos",
        "eyebrow": "Trabajo",
        "title": "Proyectos visibles",
        "description": "Productos, laboratorios y webs que puedo enseñar.",
        "iconKey": "code",
        "orbit": "inner",
        "angle": 0,
        "order": 20,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
    {
        "id": "personal",
        "route": "personal",
        "label": "Personal",
        "eyebrow": "Publicaciones",
        "title": "Notas personales",
        "description": "Espacio para publicar ideas, avances y aprendizajes.",
        "iconKey": "user",
        "orbit": "inner",
        "angle": 90,
        "order": 30,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
    {
        "id": "docs",
        "route": "docs",
        "label": "Docs",
        "eyebrow": "Biblioteca",
        "title": "Documentación",
        "description": "Accesos a guías, recursos y webs técnicas.",
        "iconKey": "book",
        "orbit": "inner",
        "angle": 180,
        "order": 40,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
]

MOMENTARY_TABS = [
    {
        "id": "references",
        "label": "Referencias",
        "iconKey": "book",
        "angle": -35,
        "order": 10,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
    {
        "id": "opportunities",
        "label": "Oportunidades",
        "iconKey": "rocket",
        "angle": 55,
        "order": 20,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
    {
        "id": "events",
        "label": "Eventos",
        "iconKey": "newspaper",
        "angle": 145,
        "order": 30,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
    {
        "id": "ideas",
        "label": "Ideas",
        "iconKey": "layers",
        "angle": 235,
        "order": 40,
        "visibleFrom": None,
        "visibleUntil": None,
        "enabled": True,
    },
]


def section_items() -> list[dict[str, object]]:
    items: list[dict[str, object]] = [
        {
            "id": "cv-summary",
            "sectionId": "cv",
            "kind": "card",
            "kicker": "Perfil",
            "title": "Resumen profesional",
            "meta": None,
            "description": CV["summary"],
            "href": None,
            "tags": CV["skills"],
            "iconKey": "briefcase",
            "order": 10,
            "visibleFrom": None,
            "visibleUntil": None,
            "featured": False,
        }
    ]

    for index, item in enumerate(CV["experience"], start=1):
        items.append(
            {
                "id": f"experience-{index}",
                "sectionId": "cv",
                "kind": "experience",
                "kicker": item["period"],
                "title": item["title"],
                "meta": item["company"],
                "description": item["description"],
                "href": None,
                "tags": [],
                "iconKey": "briefcase",
                "order": 10 + index,
                "visibleFrom": None,
                "visibleUntil": None,
                "featured": False,
            }
        )

    for index, item in enumerate(CV["education"], start=1):
        items.append(
            {
                "id": f"education-{index}",
                "sectionId": "cv",
                "kind": "education",
                "kicker": "Formación",
                "title": item["title"],
                "meta": None,
                "description": item["detail"],
                "href": None,
                "tags": [],
                "iconKey": "rocket",
                "order": 30 + index,
                "visibleFrom": None,
                "visibleUntil": None,
                "featured": False,
            }
        )

    for index, project in enumerate(PROJECTS, start=1):
        items.append(
            {
                "id": f"project-{index}",
                "sectionId": "projects",
                "kind": "project",
                "kicker": project["category"],
                "title": project["name"],
                "meta": project["status"],
                "description": project["summary"],
                "href": project["href"],
                "tags": project["stack"],
                "iconKey": "code",
                "order": index,
                "visibleFrom": None,
                "visibleUntil": None,
                "featured": project["featured"],
            }
        )

    for index, post in enumerate(POSTS, start=1):
        items.append(
            {
                "id": f"post-{index}",
                "sectionId": "personal",
                "kind": "post",
                "kicker": post["date"],
                "title": post["title"],
                "meta": None,
                "description": post["excerpt"],
                "href": post["href"],
                "tags": [],
                "iconKey": "user",
                "order": index,
                "visibleFrom": None,
                "visibleUntil": None,
                "featured": False,
            }
        )

    for index, project in enumerate([project for project in PROJECTS if project["featured"]], start=1):
        items.append(
            {
                "id": f"focus-{index}",
                "sectionId": "personal",
                "kind": "focus",
                "kicker": "Ahora mismo",
                "title": project["name"],
                "meta": project["status"],
                "description": project["summary"],
                "href": project["href"],
                "tags": project["stack"],
                "iconKey": "layers",
                "order": 20 + index,
                "visibleFrom": None,
                "visibleUntil": None,
                "featured": True,
            }
        )

    for index, doc in enumerate(DOCS, start=1):
        items.append(
            {
                "id": f"doc-{index}",
                "sectionId": "docs",
                "kind": "doc",
                "kicker": "Documento",
                "title": doc["title"],
                "meta": None,
                "description": doc["description"],
                "href": doc["href"],
                "tags": [],
                "iconKey": "newspaper",
                "order": index,
                "visibleFrom": None,
                "visibleUntil": None,
                "featured": False,
            }
        )

    return items


def content_config_payload() -> dict[str, object]:
    return {
        "sections": SECTIONS,
        "sectionItems": section_items(),
        "momentaryTabs": MOMENTARY_TABS,
    }

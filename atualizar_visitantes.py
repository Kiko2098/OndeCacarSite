"""Consulta a GraphQL Analytics API da Cloudflare e grava o número de
visitantes únicos de Portugal (PT) dos últimos 14 dias em visitantes.json
(raiz do site).

Variáveis de ambiente necessárias:
  CLOUDFLARE_API_TOKEN — token com permissão "Zone > Analytics > Read"
  CLOUDFLARE_ZONE_ID    — Zone ID do domínio (dashboard Cloudflare → Overview)

Uso: python atualizar_visitantes.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

DIAS = 14
PAIS = "PT"  # ISO 3166-1 alpha-2 — filtra visitantes só de Portugal
CAMINHO_SAIDA = os.path.join(os.path.dirname(__file__), "visitantes.json")

QUERY = """
query Visitantes($zoneTag: string, $desde: string, $ate: string, $pais: string) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      httpRequests1dGroups(
        limit: 1
        filter: { date_geq: $desde, date_leq: $ate, clientCountryName: $pais }
      ) {
        uniq { uniques }
        sum { requests pageViews }
      }
    }
  }
}
"""


def consultar_cloudflare(token, zone_id):
    hoje = date.today()
    desde = hoje - timedelta(days=DIAS)

    corpo = json.dumps({
        "query": QUERY,
        "variables": {
            "zoneTag": zone_id,
            "desde": desde.isoformat(),
            "ate": hoje.isoformat(),
            "pais": PAIS,
        },
    }).encode("utf-8")

    pedido = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/graphql",
        data=corpo,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(pedido, timeout=30) as resp:
        resultado = json.load(resp)

    if resultado.get("errors"):
        raise RuntimeError(f"Erro da API Cloudflare: {resultado['errors']}")

    zonas = resultado["data"]["viewer"]["zones"]
    if not zonas or not zonas[0]["httpRequests1dGroups"]:
        return {"visitantes": 0, "pageviews": 0}

    grupo = zonas[0]["httpRequests1dGroups"][0]
    return {
        "visitantes": grupo["uniq"]["uniques"],
        "pageviews": grupo["sum"]["pageViews"],
    }


def main():
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    zone_id = os.environ["CLOUDFLARE_ZONE_ID"]

    dados = consultar_cloudflare(token, zone_id)
    saida = {
        "gerado_em": date.today().isoformat(),
        "periodo_dias": DIAS,
        "visitantes": dados["visitantes"],
        "pageviews": dados["pageviews"],
    }

    with open(CAMINHO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"visitantes.json atualizado: {saida}")


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"Variável de ambiente em falta: {e}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"Erro ao contactar a API da Cloudflare: {e}", file=sys.stderr)
        sys.exit(1)

from app.main import app
from app.services.analysis import (
    CALIBRAZIONE_XG_INTERCETTA,
    CALIBRAZIONE_XG_PENDENZA,
    get_calibrazione_xg,
)
from app.services.competitions import COMPETITIONS


EXPECTED_SLUGS = (
    "serie-a",
    "premier-league",
    "la-liga",
    "bundesliga",
    "ligue-1",
)


def main():
    assert app.version == "0.7.0", app.version

    for slug in EXPECTED_SLUGS:
        config = COMPETITIONS[slug]
        calibrazione = get_calibrazione_xg(slug)

        assert config["model_validated"] is True, slug
        assert calibrazione["validata"] is True, slug
        assert (
            calibrazione["intercetta"]
            == CALIBRAZIONE_XG_INTERCETTA
        ), slug
        assert (
            calibrazione["pendenza"]
            == CALIBRAZIONE_XG_PENDENZA
        ), slug

        print(
            f"PASS {config['name']}: "
            f"a={calibrazione['intercetta']:.6f}, "
            f"b={calibrazione['pendenza']:.6f}, "
            "validata=True"
        )

    print("PASS Football AI v0.7.0 multi-league release configuration")


if __name__ == "__main__":
    main()

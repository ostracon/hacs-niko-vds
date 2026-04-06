"""Unit tests for the Niko VDS camera entity."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.niko_vds.camera import NikoVdsCamera
from custom_components.niko_vds.models import NikoVdsDevice


def make_camera() -> NikoVdsCamera:
    """Create a camera entity with a minimal coordinator stub."""
    mac_address = "00112a653d81"
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            devices={
                mac_address: NikoVdsDevice(
                    mac_address=mac_address,
                    name="Front Door VDS",
                    ip_address="10.0.0.10",
                    product_id="550-22001",
                    software_version="3.2.13+8000",
                    number_of_buttons=1,
                )
            },
            images={mac_address: b"\xff\xd8\xfftest"},
            content_types={mac_address: "image/jpeg"},
            errors={},
        ),
        last_update_success=True,
        client=SimpleNamespace(
            config=SimpleNamespace(controller_ip="192.0.2.1")
        ),
        async_add_listener=lambda _listener: (lambda: None),
    )
    return NikoVdsCamera(coordinator, "FP001122334455", mac_address)


def test_camera_init_sets_home_assistant_camera_state() -> None:
    """Camera.__init__ should run so HA camera internals exist."""
    camera = make_camera()

    assert hasattr(camera, "_webrtc_provider")


def test_camera_content_type_supports_base_class_assignment() -> None:
    """The entity should allow Camera.__init__ to assign content_type."""
    camera = make_camera()
    camera.coordinator.data.content_types = {}

    camera.content_type = "image/png"

    assert camera.content_type == "image/png"

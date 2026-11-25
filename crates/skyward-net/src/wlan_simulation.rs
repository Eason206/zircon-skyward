//! Explicit WLAN simulation for QEMU UI previews. No network I/O occurs.

use crate::reach::Reach;
use crate::supplicant::Security;
use crate::wlan::{Bands, Joined, Link, Network, Power, Stage, Wlan};
use std::net::Ipv4Addr;

pub const PASSWORD: &str = "qemu-demo";

#[derive(Default)]
pub struct Simulation {
    state: Wlan,
}

impl Simulation {
    pub fn state(&self) -> &Wlan {
        &self.state
    }

    pub fn power(&mut self, on: bool) {
        self.state = Wlan { power: if on { Power::On } else { Power::Off }, ..Wlan::default() };
        self.scan();
    }

    pub fn scan(&mut self) {
        if self.state.power != Power::On {
            return;
        }
        self.state.networks = [
            ("QEMU-Skyward", Security::Psk, -36, 5180),
            ("QEMU-Open", Security::Open, -54, 2412),
            ("QEMU-WPA3", Security::Sae, -67, 5975),
        ]
        .map(|(name, security, signal, frequency)| Network {
            ssid: name.as_bytes().to_vec(), name: name.into(), security, signal, frequency, bands: Bands::of(frequency),
        })
        .to_vec();
    }

    pub fn join(&mut self, ssid: &[u8], security: Security, password: &str) {
        if self.state.power != Power::On {
            return;
        }
        let network = self.state.networks.iter().find(|network| network.ssid == ssid);
        let stage = match network {
            None => Stage::NotFound,
            Some(network) if network.security != security => Stage::Failed,
            Some(network) if network.security != Security::Open && password != PASSWORD => Stage::WrongPassword,
            Some(network) => Stage::Connected(Link {
                address: Ipv4Addr::new(192, 0, 2, 2), mask: Ipv4Addr::new(255, 255, 255, 0), router: None, dns: Vec::new(),
                signal: network.signal, frequency: network.frequency, speed: None, generation: None,
                mac: "02:00:00:00:00:02".into(),
                reach: Some(Reach::Offline("QEMU simulation has no radio or internet connection".into())),
            }),
        };
        self.state.joined = Some(Joined {
            ssid: ssid.to_vec(), name: String::from_utf8_lossy(ssid).into_owned(), security, stage,
        });
    }

    pub fn leave(&mut self) {
        self.state.joined = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scanning_only_lists_qemu_hotspots_while_powered_on() {
        let mut simulation = Simulation::default();
        simulation.scan();
        assert!(simulation.state().networks.is_empty());
        simulation.power(true);
        assert_eq!(simulation.state().networks.len(), 3);
        assert!(simulation.state().networks.iter().all(|network| network.name.starts_with("QEMU-")));
        simulation.power(false);
        assert_eq!(simulation.state(), &Wlan::default());
    }

    #[test]
    fn a_password_is_checked_without_granting_internet_access() {
        let mut simulation = Simulation::default();
        simulation.power(true);
        simulation.join(b"QEMU-Skyward", Security::Psk, "wrong-password");
        assert_eq!(simulation.state().joined.as_ref().unwrap().stage, Stage::WrongPassword);
        simulation.join(b"QEMU-Skyward", Security::Psk, PASSWORD);
        let Stage::Connected(link) = &simulation.state().joined.as_ref().unwrap().stage else { panic!("simulation joins") };
        assert!(matches!(link.reach, Some(Reach::Offline(_))));
        assert!(link.dns.is_empty() && link.router.is_none());
    }

    #[test]
    fn open_networks_can_be_joined_and_forgotten() {
        let mut simulation = Simulation::default();
        simulation.power(true);
        simulation.join(b"QEMU-Open", Security::Open, "");
        assert!(matches!(simulation.state().joined.as_ref().unwrap().stage, Stage::Connected(_)));
        simulation.leave();
        assert!(simulation.state().joined.is_none());
        assert_eq!(simulation.state().power, Power::On);
    }

    #[test]
    fn unknown_hotspots_are_never_shown_as_connected() {
        let mut simulation = Simulation::default();
        simulation.power(true);
        simulation.join(b"a-real-hotspot", Security::Psk, PASSWORD);
        assert_eq!(simulation.state().joined.as_ref().unwrap().stage, Stage::NotFound);
    }
}

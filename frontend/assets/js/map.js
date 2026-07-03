(function (window, document) {
  "use strict";

  const API = window.EnergyAPI;
  const UI = window.EnergyUI;

  const DEFAULT_CENTER = [22.5, 78.0];
  const DEFAULT_ZOOM = 4.35;

  const state = {
    map: null,
    layerGroups: {},
    collections: {
      suppliers: null,
      corridors: null,
      ports: null,
      refineries: null,
      shipments: null,
      riskHotspots: null,
    },
    summary: {},
    selectedFeature: null,
    selectedKind: null,
    loading: true,
  };

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function formatNumber(value, digits = 0) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "--";
    }
    return number.toLocaleString(undefined, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function formatDate(value) {
    if (!value) {
      return "--";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }
    return parsed.toLocaleString();
  }

  function collection(features) {
    return { type: "FeatureCollection", features: Array.isArray(features) ? features : [] };
  }

  function feature(geometryType, coordinates, properties) {
    return {
      type: "Feature",
      geometry: { type: geometryType, coordinates },
      properties: properties || {},
    };
  }

  function normalizeCollection(value) {
    if (!value) {
      return collection([]);
    }
    if (Array.isArray(value)) {
      return collection(value);
    }
    if (value.type === "FeatureCollection") {
      return collection(value.features);
    }
    if (Array.isArray(value.features)) {
      return collection(value.features);
    }
    return collection([]);
  }

  function colorForRisk(level) {
    const normalized = String(level || "").toLowerCase();
    if (normalized === "critical") return "#ff6b7a";
    if (normalized === "high") return "#ffbd59";
    if (normalized === "moderate" || normalized === "medium") return "#17d2c8";
    return "#5fb6ff";
  }

  function layerKind(feature) {
    return String(feature?.properties?.layer || "").toLowerCase();
  }

  function riskLevel(score) {
    const value = Number(score || 0);
    if (value >= 80) return "critical";
    if (value >= 60) return "high";
    if (value >= 35) return "moderate";
    return "low";
  }

  function formatDetailValue(value) {
    if (Array.isArray(value)) {
      return value.length ? value.join(", ") : "--";
    }
    if (value === null || value === undefined || value === "") {
      return "--";
    }
    if (typeof value === "number") {
      return formatNumber(value, Number.isInteger(value) ? 0 : 2);
    }
    return String(value);
  }

  function buildDemoData() {
    const suppliers = collection([
      feature("Point", [45.0792, 23.8859], {
        layer: "suppliers",
        id: 1,
        label: "Saudi Arabia",
        region: "Middle East",
        status: "active",
        risk_score: 72,
        risk_level: "high",
        shipment_count: 4,
        crude_grade_types: ["Arab Light", "Arab Medium"],
      }),
      feature("Point", [43.6793, 33.2232], {
        layer: "suppliers",
        id: 2,
        label: "Iraq",
        region: "Middle East",
        status: "active",
        risk_score: 63,
        risk_level: "high",
        shipment_count: 3,
        crude_grade_types: ["Basrah Light", "Basrah Heavy"],
      }),
      feature("Point", [53.8478, 23.4241], {
        layer: "suppliers",
        id: 3,
        label: "UAE",
        region: "Middle East",
        status: "active",
        risk_score: 49,
        risk_level: "moderate",
        shipment_count: 3,
        crude_grade_types: ["Murban", "Upper Zakum"],
      }),
      feature("Point", [105.3188, 61.5240], {
        layer: "suppliers",
        id: 4,
        label: "Russia",
        region: "Europe/Eurasia",
        status: "active",
        risk_score: 84,
        risk_level: "critical",
        shipment_count: 2,
        crude_grade_types: ["Urals"],
      }),
      feature("Point", [8.6753, 9.0820], {
        layer: "suppliers",
        id: 5,
        label: "Nigeria",
        region: "Africa",
        status: "active",
        risk_score: 41,
        risk_level: "moderate",
        shipment_count: 2,
        crude_grade_types: ["Bonny Light"],
      }),
      feature("Point", [-95.7129, 37.0902], {
        layer: "suppliers",
        id: 6,
        label: "USA",
        region: "North America",
        status: "active",
        risk_score: 28,
        risk_level: "low",
        shipment_count: 1,
        crude_grade_types: ["WTI", "Mars"],
      }),
    ]);

    const corridors = collection([
      feature("LineString", [[56.2, 25.1], [58.9, 24.7], [68.0, 22.6], [72.0, 18.9]], {
        layer: "corridors",
        id: 1,
        label: "Strait of Hormuz",
        corridor_type: "maritime",
        status: "watchlist",
        risk_score: 88,
        risk_level: "critical",
        typical_transit_days: 8,
        shipment_count: 4,
        notes: "High choke-point exposure and regional escalation risk.",
      }),
      feature("LineString", [[32.0, 30.0], [36.5, 27.2], [42.0, 15.5], [47.0, 12.4]], {
        layer: "corridors",
        id: 2,
        label: "Red Sea",
        corridor_type: "maritime",
        status: "disrupted",
        risk_score: 81,
        risk_level: "critical",
        typical_transit_days: 14,
        shipment_count: 3,
        notes: "Diversion and security patrol pressure remain elevated.",
      }),
      feature("LineString", [[18.0, -34.0], [23.0, -22.0], [40.0, -5.0], [68.0, 12.5], [72.0, 20.0]], {
        layer: "corridors",
        id: 3,
        label: "Cape of Good Hope",
        corridor_type: "diversion",
        status: "open",
        risk_score: 44,
        risk_level: "moderate",
        typical_transit_days: 22,
        shipment_count: 2,
        notes: "Longer route used during Red Sea disruptions.",
      }),
    ]);

    const ports = collection([
      feature("Point", [69.7330, 22.4200], {
        layer: "ports",
        id: 1,
        label: "Vadinar",
        country: "India",
        status: "active",
        port_type: "refinery port",
        risk_score: 61,
        risk_level: "high",
        congestion_score: 0.42,
        shipment_count: 3,
      }),
      feature("Point", [70.0700, 22.4900], {
        layer: "ports",
        id: 2,
        label: "Jamnagar",
        country: "India",
        status: "active",
        port_type: "refinery port",
        risk_score: 58,
        risk_level: "moderate",
        congestion_score: 0.35,
        shipment_count: 4,
      }),
      feature("Point", [72.8780, 19.0760], {
        layer: "ports",
        id: 3,
        label: "Mumbai Port",
        country: "India",
        status: "active",
        port_type: "import port",
        risk_score: 33,
        risk_level: "low",
        congestion_score: 0.22,
        shipment_count: 2,
      }),
      feature("Point", [86.4400, 20.2500], {
        layer: "ports",
        id: 4,
        label: "Paradip",
        country: "India",
        status: "active",
        port_type: "import port",
        risk_score: 39,
        risk_level: "moderate",
        congestion_score: 0.27,
        shipment_count: 2,
      }),
      feature("Point", [56.3050, 25.1840], {
        layer: "ports",
        id: 5,
        label: "Fujairah",
        country: "UAE",
        status: "active",
        port_type: "export port",
        risk_score: 69,
        risk_level: "high",
        congestion_score: 0.31,
        shipment_count: 3,
      }),
    ]);

    const refineries = collection([
      feature("Point", [70.0900, 22.3500], {
        layer: "refineries",
        id: 1,
        label: "Jamnagar Refinery",
        company: "Reliance",
        state: "Gujarat",
        status: "active",
        risk_score: 74,
        risk_level: "high",
        capacity_bpd: 1240000,
        strategic_priority_score: 9.5,
        linked_port_name: "Jamnagar",
        compatible_crude_grades: ["Arab Light", "Basrah Light", "Murban"],
      }),
      feature("Point", [69.6400, 22.4300], {
        layer: "refineries",
        id: 2,
        label: "Vadinar Refinery",
        company: "Nayara",
        state: "Gujarat",
        status: "active",
        risk_score: 68,
        risk_level: "high",
        capacity_bpd: 400000,
        strategic_priority_score: 8.4,
        linked_port_name: "Vadinar",
        compatible_crude_grades: ["Arab Heavy", "Basrah Heavy"],
      }),
      feature("Point", [76.9470, 29.0010], {
        layer: "refineries",
        id: 3,
        label: "Panipat Refinery",
        company: "IOCL",
        state: "Haryana",
        status: "active",
        risk_score: 46,
        risk_level: "moderate",
        capacity_bpd: 150000,
        strategic_priority_score: 7.2,
        linked_port_name: null,
        compatible_crude_grades: ["Arab Light", "Urals"],
      }),
      feature("Point", [73.0000, 18.9100], {
        layer: "refineries",
        id: 4,
        label: "Mumbai Refinery",
        company: "HPCL",
        state: "Maharashtra",
        status: "active",
        risk_score: 37,
        risk_level: "moderate",
        capacity_bpd: 190000,
        strategic_priority_score: 6.8,
        linked_port_name: "Mumbai Port",
        compatible_crude_grades: ["WTI", "Murban"],
      }),
    ]);

    const shipments = collection([
      feature("LineString", [[56.3050, 25.1840], [69.7330, 22.4200]], {
        layer: "shipments",
        id: 1,
        label: "Tanker Orion",
        status: "in_transit",
        risk_flag: true,
        risk_score: 79,
        risk_level: "high",
        cargo_volume_bbl: 820000,
        crude_grade: "Arab Light",
        eta: new Date(Date.now() + 3 * 86400000).toISOString(),
        freight_cost: 4.2,
      }),
      feature("LineString", [[43.5, 29.0], [69.6400, 22.4300]], {
        layer: "shipments",
        id: 2,
        label: "Tanker Horizon",
        status: "delayed",
        risk_flag: true,
        risk_score: 83,
        risk_level: "critical",
        cargo_volume_bbl: 620000,
        crude_grade: "Basrah Heavy",
        eta: new Date(Date.now() + 6 * 86400000).toISOString(),
        freight_cost: 5.1,
      }),
      feature("LineString", [[8.6753, 9.0820], [72.8780, 19.0760]], {
        layer: "shipments",
        id: 3,
        label: "Tanker Delta",
        status: "scheduled",
        risk_flag: false,
        risk_score: 41,
        risk_level: "moderate",
        cargo_volume_bbl: 510000,
        crude_grade: "Bonny Light",
        eta: new Date(Date.now() + 5 * 86400000).toISOString(),
        freight_cost: 4.7,
      }),
      feature("LineString", [[105.3188, 61.5240], [86.4400, 20.2500]], {
        layer: "shipments",
        id: 4,
        label: "Tanker Aurora",
        status: "in_transit",
        risk_flag: true,
        risk_score: 88,
        risk_level: "critical",
        cargo_volume_bbl: 690000,
        crude_grade: "Urals",
        eta: new Date(Date.now() + 12 * 86400000).toISOString(),
        freight_cost: 6.3,
      }),
    ]);

    const riskOverlays = collection([
      feature("Point", [56.3050, 25.1840], {
        layer: "risk_overlays",
        id: "overlay-hormuz",
        label: "Hormuz risk cloud",
        overlay_type: "corridor_risk",
        risk_score: 91,
        risk_level: "critical",
        radius_km: 270,
      }),
      feature("Point", [38.0, 20.5], {
        layer: "risk_overlays",
        id: "overlay-redsea",
        label: "Red Sea risk cloud",
        overlay_type: "corridor_risk",
        risk_score: 84,
        risk_level: "critical",
        radius_km: 320,
      }),
      feature("Point", [70.0900, 22.3500], {
        layer: "risk_overlays",
        id: "overlay-jamnagar",
        label: "Jamnagar cluster",
        overlay_type: "refinery_risk",
        risk_score: 76,
        risk_level: "high",
        radius_km: 180,
      }),
    ]);

    const riskHotspots = collection([
      feature("Point", [56.3050, 25.1840], {
        layer: "risk_hotspots",
        id: "hotspot-hormuz",
        label: "Strait of Hormuz",
        overlay_type: "corridor_risk",
        risk_score: 92,
        risk_level: "critical",
        radius_km: 300,
      }),
      feature("Point", [38.0, 20.5], {
        layer: "risk_hotspots",
        id: "hotspot-redsea",
        label: "Red Sea",
        overlay_type: "corridor_risk",
        risk_score: 86,
        risk_level: "critical",
        radius_km: 340,
      }),
      feature("Point", [70.0900, 22.3500], {
        layer: "risk_hotspots",
        id: "hotspot-jamnagar",
        label: "Jamnagar cluster",
        overlay_type: "refinery_risk",
        risk_score: 78,
        risk_level: "high",
        radius_km: 200,
      }),
      feature("Point", [69.6400, 22.4300], {
        layer: "risk_hotspots",
        id: "hotspot-vadinar",
        label: "Vadinar cluster",
        overlay_type: "refinery_risk",
        risk_score: 72,
        risk_level: "high",
        radius_km: 160,
      }),
      feature("Point", [86.4400, 20.2500], {
        layer: "risk_hotspots",
        id: "hotspot-paradip",
        label: "Paradip approach",
        overlay_type: "port_risk",
        risk_score: 63,
        risk_level: "high",
        radius_km: 130,
      }),
    ]);

    return {
      summary: {
        supplier_count: suppliers.features.length,
        corridor_count: corridors.features.length,
        port_count: ports.features.length,
        refinery_count: refineries.features.length,
        shipment_count: shipments.features.length,
        risk_hotspot_count: riskHotspots.features.length,
      },
      layers: {
        suppliers,
        corridors,
        ports,
        refineries,
        shipments,
        risk_overlays: riskOverlays,
        risk_hotspots: riskHotspots,
      },
    };
  }

  function ensureMap() {
    if (state.map || !window.L) {
      return state.map;
    }

    state.map = window.L.map("map-view", {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      minZoom: 2,
      worldCopyJump: true,
      zoomControl: true,
      preferCanvas: true,
    });

    window.L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(state.map);

    state.layerGroups = {
      suppliers: window.L.featureGroup().addTo(state.map),
      corridors: window.L.featureGroup().addTo(state.map),
      ports: window.L.featureGroup().addTo(state.map),
      refineries: window.L.featureGroup().addTo(state.map),
      shipments: window.L.featureGroup().addTo(state.map),
      riskHotspots: window.L.featureGroup().addTo(state.map),
    };

    return state.map;
  }

  function clearLayerGroups() {
    Object.values(state.layerGroups).forEach((group) => {
      if (group) {
        group.clearLayers();
      }
    });
  }

  function popupHtml(feature, kind) {
    const properties = feature.properties || {};
    const title = UI.escapeHtml(properties.label || properties.name || kind || "Feature");
    const riskScore = formatNumber(properties.risk_score, 1);
    const computedRiskLevel = UI.escapeHtml(properties.risk_level || riskLevel(properties.risk_score));

    const lines = [];
    if (kind === "suppliers") {
      lines.push(["Region", properties.region]);
      lines.push(["Shipments", properties.shipment_count]);
      lines.push(["Crude grades", properties.crude_grade_types]);
      lines.push(["Status", properties.status]);
    } else if (kind === "corridors") {
      lines.push(["Type", properties.corridor_type]);
      lines.push(["Status", properties.status]);
      lines.push(["Transit days", properties.typical_transit_days]);
      lines.push(["Shipments", properties.shipment_count]);
      lines.push(["Notes", properties.notes]);
    } else if (kind === "ports") {
      lines.push(["Country", properties.country]);
      lines.push(["Type", properties.port_type]);
      lines.push(["Congestion", properties.congestion_score]);
      lines.push(["Shipments", properties.shipment_count]);
    } else if (kind === "refineries") {
      lines.push(["Company", properties.company]);
      lines.push(["State", properties.state]);
      lines.push(["Capacity", properties.capacity_bpd]);
      lines.push(["Strategic priority", properties.strategic_priority_score]);
      lines.push(["Linked port", properties.linked_port_name]);
      lines.push(["Compatible grades", properties.compatible_crude_grades]);
    } else if (kind === "shipments") {
      lines.push(["Status", properties.status]);
      lines.push(["Cargo", properties.cargo_volume_bbl]);
      lines.push(["Crude grade", properties.crude_grade]);
      lines.push(["ETA", formatDate(properties.eta)]);
      lines.push(["Freight", properties.freight_cost]);
      lines.push(["Risk flag", properties.risk_flag ? "Yes" : "No"]);
    } else {
      lines.push(["Overlay type", properties.overlay_type]);
      lines.push(["Radius", properties.radius_km ? `${formatNumber(properties.radius_km, 0)} km` : "--"]);
    }

    return `
      <div class="map-popup__title">
        <div>
          <strong>${title}</strong>
          <span>${UI.escapeHtml(kind || "feature")}</span>
        </div>
        <span class="pill ${computedRiskLevel === "critical" ? "pill--critical" : computedRiskLevel === "high" ? "pill--high" : computedRiskLevel === "moderate" ? "pill--moderate" : "pill--low"}">${riskScore}</span>
      </div>
      <div class="map-popup__body">
        ${lines
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .map(
            ([label, value]) => `
              <div><span>${UI.escapeHtml(label)}</span><strong>${UI.escapeHtml(formatDetailValue(value))}</strong></div>
            `,
          )
          .join("")}
      </div>
    `;
  }

  function detailRows(feature, kind) {
    const properties = feature.properties || {};
    const rows = [];
    rows.push({ label: "Type", value: kind || properties.layer || "feature" });
    rows.push({ label: "Risk level", value: properties.risk_level || riskLevel(properties.risk_score) });
    rows.push({ label: "Risk score", value: formatNumber(properties.risk_score, 1) });

    if (kind === "suppliers") {
      rows.push({ label: "Region", value: properties.region });
      rows.push({ label: "Shipment count", value: properties.shipment_count });
      rows.push({ label: "Crude grades", value: properties.crude_grade_types });
    } else if (kind === "corridors") {
      rows.push({ label: "Status", value: properties.status });
      rows.push({ label: "Transit days", value: properties.typical_transit_days });
      rows.push({ label: "Shipment count", value: properties.shipment_count });
      rows.push({ label: "Notes", value: properties.notes });
    } else if (kind === "ports") {
      rows.push({ label: "Country", value: properties.country });
      rows.push({ label: "Port type", value: properties.port_type });
      rows.push({ label: "Congestion", value: properties.congestion_score });
      rows.push({ label: "Shipment count", value: properties.shipment_count });
    } else if (kind === "refineries") {
      rows.push({ label: "Company", value: properties.company });
      rows.push({ label: "State", value: properties.state });
      rows.push({ label: "Capacity bpd", value: properties.capacity_bpd });
      rows.push({ label: "Priority score", value: properties.strategic_priority_score });
      rows.push({ label: "Linked port", value: properties.linked_port_name });
      rows.push({ label: "Compatible grades", value: properties.compatible_crude_grades });
    } else if (kind === "shipments") {
      rows.push({ label: "Status", value: properties.status });
      rows.push({ label: "Cargo bbl", value: properties.cargo_volume_bbl });
      rows.push({ label: "Crude grade", value: properties.crude_grade });
      rows.push({ label: "ETA", value: formatDate(properties.eta) });
      rows.push({ label: "Freight cost", value: properties.freight_cost });
      rows.push({ label: "Risk flag", value: properties.risk_flag ? "Yes" : "No" });
    } else {
      rows.push({ label: "Overlay type", value: properties.overlay_type });
      rows.push({ label: "Radius km", value: properties.radius_km });
    }

    return rows;
  }

  function updateSelection(feature, kind) {
    state.selectedFeature = feature;
    state.selectedKind = kind;

    const element = qs("#map-selection");
    if (!element) {
      return;
    }

    if (!feature) {
      element.innerHTML = `
        <div class="panel map-detail-card">
          <div class="panel__header">
            <div>
              <p class="eyebrow">Selection</p>
              <h2>No feature selected</h2>
            </div>
            <span class="badge">Inspect details</span>
          </div>
          <p>Select a port, refinery, shipment route, corridor, or hotspot to inspect the route intelligence.</p>
        </div>
      `;
      return;
    }

    const properties = feature.properties || {};
    const title = UI.escapeHtml(properties.label || properties.name || kind || "Selected feature");
    const rows = detailRows(feature, kind);

    element.innerHTML = `
      <div class="panel map-detail-card">
        <div class="panel__header">
          <div>
            <p class="eyebrow">Selection</p>
            <h2>${title}</h2>
          </div>
          <span class="badge ${riskLevel(properties.risk_score) === "critical" ? "badge--critical" : riskLevel(properties.risk_score) === "high" ? "badge--warning" : "badge--success"}">${UI.escapeHtml(riskLevel(properties.risk_score))}</span>
        </div>
        <div class="map-detail-list">
          ${rows
            .map(
              (row) => `
                <div class="map-detail-row">
                  <span>${UI.escapeHtml(row.label)}</span>
                  <strong>${UI.escapeHtml(formatDetailValue(row.value))}</strong>
                </div>
              `,
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function attachFeatureBehaviour(layer, feature, kind) {
    layer.on("click", () => {
      updateSelection(feature, kind);
    });
    layer.on("popupopen", () => {
      updateSelection(feature, kind);
    });
  }

  function pointToLayer(feature, latlng, kind) {
    const properties = feature.properties || {};
    const score = Number(properties.risk_score || 0);
    const level = properties.risk_level || riskLevel(score);
    const color = colorForRisk(level);

    if (kind === "riskHotspots") {
      return window.L.circle(latlng, {
        radius: Math.max(5000, Number(properties.radius_km || 0) * 1000),
        color,
        weight: 2,
        opacity: 0.9,
        fillColor: color,
        fillOpacity: 0.16,
      });
    }

    const sizeBase = kind === "refineries" ? 9 : kind === "ports" ? 8 : kind === "suppliers" ? 7 : 7;
    const radius = sizeBase + Math.min(6, Math.max(0, score / 18));

    return window.L.circleMarker(latlng, {
      radius,
      color: "#eff6ff",
      weight: 1.5,
      opacity: 0.85,
      fillColor: color,
      fillOpacity: kind === "shipments" ? 0.75 : 0.9,
    });
  }

  function styleForFeature(feature, kind) {
    const properties = feature.properties || {};
    const score = Number(properties.risk_score || 0);
    const level = properties.risk_level || riskLevel(score);
    const color = colorForRisk(level);

    if (kind === "riskHotspots") {
      return {
        color,
        weight: 6,
        opacity: 0.5,
        dashArray: "10 10",
      };
    }

    if (kind === "shipments") {
      return {
        color,
        weight: Math.max(3, Math.min(8, 3 + score / 20)),
        opacity: 0.85,
        dashArray: properties.risk_flag || String(properties.status || "").toLowerCase() === "delayed" ? "8 8" : null,
      };
    }

    if (kind === "corridors") {
      const disrupted = String(properties.status || "").toLowerCase() !== "open";
      return {
        color,
        weight: disrupted ? 6 : 4,
        opacity: 0.9,
        dashArray: disrupted ? "10 10" : null,
      };
    }

    return {
      color,
      weight: 3,
      opacity: 0.8,
    };
  }

  function addGeoJsonLayer(kind, collectionValue) {
    const group = state.layerGroups[kind];
    if (!group) {
      return;
    }

    group.clearLayers();

    const data = normalizeCollection(collectionValue);
    if (!data.features.length) {
      return;
    }

    const layer = window.L.geoJSON(data, {
      pointToLayer: (feature, latlng) => pointToLayer(feature, latlng, kind),
      style: (feature) => styleForFeature(feature, kind),
      onEachFeature: (feature, layer) => {
        layer.bindPopup(popupHtml(feature, kind), {
          className: "map-popup",
          maxWidth: 360,
          closeButton: true,
        });
        attachFeatureBehaviour(layer, feature, kind);
      },
    });

    group.addLayer(layer);
  }

  function updateSummary() {
    const summary = state.summary || {};
    const values = {
      supplier: summary.supplier_count || state.collections.suppliers?.features?.length || 0,
      corridor: summary.corridor_count || state.collections.corridors?.features?.length || 0,
      port: summary.port_count || state.collections.ports?.features?.length || 0,
      refinery: summary.refinery_count || state.collections.refineries?.features?.length || 0,
      shipment: summary.shipment_count || state.collections.shipments?.features?.length || 0,
      hotspot: summary.risk_hotspot_count || state.collections.riskHotspots?.features?.length || 0,
    };

    setText("#map-supplier-count", formatNumber(values.supplier, 0));
    setText("#map-corridor-count", formatNumber(values.corridor, 0));
    setText("#map-port-count", formatNumber(values.port, 0));
    setText("#map-refinery-count", formatNumber(values.refinery, 0));
    setText("#map-shipment-count", formatNumber(values.shipment, 0));
    setText("#map-hotspot-count", formatNumber(values.hotspot, 0));
    setText("#map-hotspot-total", `${formatNumber(values.hotspot, 0)} signals`);

    const counts = {
      suppliers: values.supplier,
      corridors: values.corridor,
      ports: values.port,
      refineries: values.refinery,
      shipments: values.shipment,
      riskHotspots: values.hotspot,
    };

    qsa("[data-map-count]").forEach((node) => {
      const key = node.getAttribute("data-map-count");
      if (counts[key] !== undefined) {
        node.textContent = formatNumber(counts[key], 0);
      }
    });
  }

  function renderHotspotList() {
    const element = qs("#map-hotspot-list");
    if (!element) {
      return;
    }

    const hotspots = normalizeCollection(state.collections.riskHotspots).features
      .slice()
      .sort((left, right) => Number(right.properties?.risk_score || 0) - Number(left.properties?.risk_score || 0))
      .slice(0, 6);

    if (!hotspots.length) {
      element.innerHTML = `
        <div class="panel state-card state-card--loading">
          <strong>No hotspots available</strong>
          <p>The current dataset does not contain elevated risk markers.</p>
        </div>
      `;
      return;
    }

    element.innerHTML = hotspots
      .map((item, index) => {
        const properties = item.properties || {};
        const level = properties.risk_level || riskLevel(properties.risk_score);
        return `
          <article class="map-hotspot-card" data-map-hotspot="${index}">
            <strong>${UI.escapeHtml(properties.label || properties.name || "Hotspot")}</strong>
            <p>${UI.escapeHtml(properties.overlay_type || properties.layer || "risk hotspot")}</p>
            <div class="map-hotspot-card__meta">
              <span>${UI.escapeHtml(level)}</span>
              <span>${formatNumber(properties.risk_score, 1)}</span>
            </div>
          </article>
        `;
      })
      .join("");

    qsa("[data-map-hotspot]", element).forEach((card, index) => {
      card.addEventListener("click", () => {
        const featureItem = hotspots[index];
        if (!featureItem) {
          return;
        }
        updateSelection(featureItem, "riskHotspots");
        focusFeature(featureItem);
      });
    });
  }

  function collectVisibleGroups() {
    return qsa("[data-map-layer]").reduce((groups, input) => {
      if (input.checked) {
        const key = input.getAttribute("data-map-layer");
        const group = state.layerGroups[key];
        if (group) {
          groups.push(group);
        }
      }
      return groups;
    }, []);
  }

  function applyVisibility() {
    if (!state.map) {
      return;
    }

    Object.entries(state.layerGroups).forEach(([key, group]) => {
      const toggle = qs(`[data-map-layer="${key}"]`);
      const shouldShow = key === "suppliers" || (toggle ? toggle.checked : true);
      if (!group) {
        return;
      }
      if (shouldShow) {
        if (!state.map.hasLayer(group)) {
          group.addTo(state.map);
        }
      } else if (state.map.hasLayer(group)) {
        state.map.removeLayer(group);
      }
    });
  }

  function fitToVisibleLayers() {
    if (!state.map) {
      return;
    }

    const visibleGroups = collectVisibleGroups().filter((group) => group.getLayers().length > 0);
    if (!visibleGroups.length) {
      state.map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
      return;
    }

    const tempGroup = window.L.featureGroup();
    visibleGroups.forEach((group) => {
      group.eachLayer((layer) => tempGroup.addLayer(layer));
    });

    const bounds = tempGroup.getBounds();
    if (bounds && bounds.isValid()) {
      state.map.fitBounds(bounds.pad(0.15));
    }
  }

  function setStatus(message, loading = false) {
    const element = qs("#map-status");
    if (element) {
      element.textContent = message;
      element.classList.toggle("map-toolbar__status--loading", Boolean(loading));
    }
    const emptyState = qs("#map-empty-state");
    if (emptyState) {
      if (loading) {
        emptyState.style.display = "block";
        emptyState.innerHTML = `
          <div class="panel state-card state-card--loading">
            <strong>Loading map data</strong>
            <p>${UI.escapeHtml(message || "Fetching geospatial intelligence...")}</p>
          </div>
        `;
      } else {
        emptyState.innerHTML = "";
        emptyState.style.display = "none";
      }
    }
  }

  function setError(message) {
    const emptyState = qs("#map-empty-state");
    if (emptyState) {
      emptyState.style.display = "block";
      emptyState.innerHTML = UI.renderErrorState(message || "Unable to load map data.", "Retry");
    }
    const status = qs("#map-status");
    if (status) {
      status.textContent = message || "Map data unavailable";
    }
  }

  function mergeCollections(baseCollection, overlayCollection) {
    const base = normalizeCollection(baseCollection);
    const overlay = normalizeCollection(overlayCollection);
    return collection([...(base.features || []), ...(overlay.features || [])]);
  }

  function buildLookups() {
    const lookup = {
      suppliers: {},
      corridors: {},
      ports: {},
      refineries: {},
    };

    normalizeCollection(state.collections.suppliers).features.forEach((item) => {
      lookup.suppliers[item.properties?.id] = item.properties?.label || "Supplier";
    });
    normalizeCollection(state.collections.corridors).features.forEach((item) => {
      lookup.corridors[item.properties?.id] = item.properties?.label || "Corridor";
    });
    normalizeCollection(state.collections.ports).features.forEach((item) => {
      lookup.ports[item.properties?.id] = item.properties?.label || "Port";
    });
    normalizeCollection(state.collections.refineries).features.forEach((item) => {
      lookup.refineries[item.properties?.id] = item.properties?.label || "Refinery";
    });

    return lookup;
  }

  function addLayerBadges() {
    const lookup = buildLookups();
    state.lookup = lookup;
  }

  function renderLayers() {
    clearLayerGroups();
    addGeoJsonLayer("suppliers", state.collections.suppliers);
    addGeoJsonLayer("corridors", state.collections.corridors);
    addGeoJsonLayer("ports", state.collections.ports);
    addGeoJsonLayer("refineries", state.collections.refineries);
    addGeoJsonLayer("shipments", state.collections.shipments);
    addGeoJsonLayer("riskHotspots", state.collections.riskHotspots);
    applyVisibility();
  }

  function focusFeature(feature) {
    if (!state.map || !feature) {
      return;
    }
    const bounds = window.L.geoJSON(feature).getBounds();
    if (bounds && bounds.isValid()) {
      state.map.fitBounds(bounds.pad(0.25));
    }
  }

  function bindControls() {
    qsa("[data-map-layer]").forEach((input) => {
      input.addEventListener("change", () => {
        applyVisibility();
      });
    });

    const refreshButton = qs("[data-map-refresh]");
    if (refreshButton) {
      refreshButton.addEventListener("click", () => loadMapData(true));
    }

    const fitButton = qs("[data-map-fit]");
    if (fitButton) {
      fitButton.addEventListener("click", fitToVisibleLayers);
    }
  }

  async function loadMapData(forceDemo = false) {
    ensureMap();
    setStatus("Loading geospatial layers...", true);
    updateSelection(null, null);

    try {
      if (forceDemo) {
        throw new Error("demo requested");
      }

      const [networkResult, shipmentsResult, corridorsResult, refineriesResult, portsResult, hotspotsResult] = await Promise.allSettled([
        API.getJson("/map/network"),
        API.getJson("/map/shipments"),
        API.getJson("/map/corridors"),
        API.getJson("/map/refineries"),
        API.getJson("/map/ports"),
        API.getJson("/map/risk-hotspots"),
      ]);

      const network = networkResult.status === "fulfilled" ? networkResult.value : null;
      const shipments = shipmentsResult.status === "fulfilled" ? shipmentsResult.value : null;
      const corridors = corridorsResult.status === "fulfilled" ? corridorsResult.value : null;
      const refineries = refineriesResult.status === "fulfilled" ? refineriesResult.value : null;
      const ports = portsResult.status === "fulfilled" ? portsResult.value : null;
      const hotspots = hotspotsResult.status === "fulfilled" ? hotspotsResult.value : null;

      state.summary = network?.summary || {};
      state.collections.suppliers = normalizeCollection(network?.layers?.suppliers);
      state.collections.corridors = normalizeCollection(corridors || network?.layers?.corridors);
      state.collections.ports = normalizeCollection(ports || network?.layers?.ports);
      state.collections.refineries = normalizeCollection(refineries || network?.layers?.refineries);
      state.collections.shipments = normalizeCollection(shipments || network?.layers?.shipments);
      state.collections.riskHotspots = mergeCollections(network?.layers?.risk_overlays, hotspots || network?.layers?.risk_hotspots);

      if (!state.collections.suppliers.features.length) {
        state.collections.suppliers = normalizeCollection(network?.layers?.suppliers);
      }

      if (!state.collections.suppliers.features.length && !state.collections.corridors.features.length) {
        throw new Error("empty map response");
      }

      addLayerBadges();
      renderLayers();
      updateSummary();
      renderHotspotList();
      fitToVisibleLayers();
      setStatus("Live map loaded from backend", false);
      if (state.map) {
        state.map.invalidateSize();
      }
    } catch (error) {
      console.warn("Falling back to demo map data", error);
      const demo = buildDemoData();
      state.summary = demo.summary;
      state.collections.suppliers = demo.layers.suppliers;
      state.collections.corridors = demo.layers.corridors;
      state.collections.ports = demo.layers.ports;
      state.collections.refineries = demo.layers.refineries;
      state.collections.shipments = demo.layers.shipments;
      state.collections.riskHotspots = mergeCollections(demo.layers.risk_overlays, demo.layers.risk_hotspots);
      addLayerBadges();
      renderLayers();
      updateSummary();
      renderHotspotList();
      fitToVisibleLayers();
      setStatus("Demo map loaded because the backend was unavailable or unauthorized.", false);
      if (state.map) {
        state.map.invalidateSize();
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (!window.L) {
      setError("Leaflet failed to load. Check the CDN connection.");
      return;
    }

    ensureMap();
    bindControls();
    loadMapData(false);
  });
})(window, document);

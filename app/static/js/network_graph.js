/**
 * N.E.S.T — D3.js Collaboration Network Graph
 * Pure D3 v7 force-directed graph.
 */
(function () {
    "use strict";

    /* ────────────────────────────────────────────
       Color palette by archetype
       ──────────────────────────────────────────── */
    const ARCHETYPE_COLORS = {
        Builder: "#6366f1",  // indigo
        Designer: "#f472b6",  // pink
        Researcher: "#22d3ee",  // cyan
        Communicator: "#facc15",  // amber
        Strategist: "#34d399",  // emerald
        Unknown: "#94a3b8",  // slate
    };

    /* ────────────────────────────────────────────
       DOM references
       ──────────────────────────────────────────── */
    const wrapper = document.getElementById("graphWrapper");
    const svg = d3.select("#networkSvg");
    const tooltip = document.getElementById("graphTooltip");
    const sidebar = document.getElementById("profileSidebar");
    const sidebarContent = document.getElementById("sidebarContent");
    const searchInput = document.getElementById("searchInput");
    const filterDept = document.getElementById("filterDept");
    const filterArch = document.getElementById("filterArchetype");
    const legendBox = document.getElementById("graphLegend");

    let width = wrapper.clientWidth;
    let height = wrapper.clientHeight;

    /* ────────────────────────────────────────────
       Fetch data & render
       ──────────────────────────────────────────── */
    fetch("/graph/data")
        .then(r => r.json())
        .then(data => render(data))
        .catch(err => console.error("Graph data fetch failed:", err));

    function render(data) {
        const { nodes, links } = data;

        if (nodes.length === 0) {
            svg.append("text")
                .attr("x", width / 2)
                .attr("y", height / 2)
                .attr("text-anchor", "middle")
                .attr("fill", "rgba(0,0,0,.3)")
                .attr("font-size", "1.2rem")
                .text("No users found. The network is empty.");
            return;
        }

        /* ── Populate filter dropdowns ── */
        const departments = [...new Set(nodes.map(n => n.department))].sort();
        const archetypes = [...new Set(nodes.map(n => n.archetype))].sort();

        departments.forEach(d => {
            const opt = document.createElement("option");
            opt.value = d; opt.textContent = d;
            filterDept.appendChild(opt);
        });
        archetypes.forEach(a => {
            const opt = document.createElement("option");
            opt.value = a; opt.textContent = a;
            filterArch.appendChild(opt);
        });

        /* ── Build legend ── */
        archetypes.forEach(a => {
            const item = document.createElement("div");
            item.className = "legend-item";
            item.innerHTML = `<span class="legend-dot" style="background:${ARCHETYPE_COLORS[a] || ARCHETYPE_COLORS.Unknown}"></span>${a}`;
            legendBox.appendChild(item);
        });

        /* ── Scales ── */
        const maxCollab = d3.max(nodes, d => d.collab_count) || 1;
        const nodeRadius = d3.scaleLinear()
            .domain([0, maxCollab])
            .range([6, 22]);

        const maxWeight = d3.max(links, d => d.weight) || 1;
        const linkWidth = d3.scaleLinear()
            .domain([1, maxWeight])
            .range([1.5, 6]);

        /* ── SVG groups (order matters for layering) ── */
        const g = svg.append("g");

        const linkGroup = g.append("g").attr("class", "links");
        const nodeGroup = g.append("g").attr("class", "nodes");

        /* ── Zoom ── */
        const zoom = d3.zoom()
            .scaleExtent([0.2, 5])
            .on("zoom", (event) => g.attr("transform", event.transform));
        svg.call(zoom);

        /* ── Simulation ── */
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-200))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => nodeRadius(d.collab_count) + 4));

        /* ── Draw links ── */
        const link = linkGroup.selectAll("line")
            .data(links)
            .join("line")
            .attr("stroke", "rgba(13, 148, 136, .35)")
            .attr("stroke-width", d => linkWidth(d.weight))
            .attr("stroke-linecap", "round");

        /* ── Draw nodes ── */
        const node = nodeGroup.selectAll("g")
            .data(nodes)
            .join("g")
            .attr("class", "node-g")
            .call(d3.drag()
                .on("start", dragStarted)
                .on("drag", dragged)
                .on("end", dragEnded));

        // Glow ring
        node.append("circle")
            .attr("r", d => nodeRadius(d.collab_count) + 3)
            .attr("fill", "none")
            .attr("stroke", d => ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown)
            .attr("stroke-width", 2)
            .attr("stroke-opacity", .3);

        // Main circle
        node.append("circle")
            .attr("r", d => nodeRadius(d.collab_count))
            .attr("fill", d => ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown)
            .attr("fill-opacity", .85)
            .attr("stroke", "#e2e8f0")
            .attr("stroke-width", 2)
            .attr("cursor", "pointer");

        // Labels (only for high-collab users to avoid clutter)
        node.append("text")
            .text(d => d.name.split(" ")[0])
            .attr("dy", d => nodeRadius(d.collab_count) + 14)
            .attr("text-anchor", "middle")
            .attr("fill", "rgba(0,0,0,.5)")
            .attr("font-size", "10px")
            .attr("pointer-events", "none");

        /* ── Tooltip handlers ── */
        node.on("mouseenter", (event, d) => {
            const capsHtml = d.capabilities.length
                ? d.capabilities.slice(0, 3).map(c => `<span class="badge bg-primary bg-opacity-50 me-1">${c}</span>`).join("")
                : "<span class='text-muted'>None</span>";

            tooltip.innerHTML = `
                    <h6>${d.name}</h6>
                    <div class="tt-label">Archetype</div>
                    <div class="mb-1">${d.archetype}</div>
                    <div class="tt-label">Department</div>
                    <div class="mb-1">${d.department}</div>
                    <div class="tt-label">Top Capabilities</div>
                    <div class="mb-1">${capsHtml}</div>
                    <div class="tt-label">Collaborations</div>
                    <div>${d.collab_count}</div>
                `;
            tooltip.classList.add("show");
        })
            .on("mousemove", (event) => {
                const rect = wrapper.getBoundingClientRect();
                let x = event.clientX - rect.left + 16;
                let y = event.clientY - rect.top + 16;
                // Keep tooltip inside wrapper
                if (x + 200 > width) x = x - 220;
                if (y + 180 > height) y = y - 200;
                tooltip.style.left = x + "px";
                tooltip.style.top = y + "px";
            })
            .on("mouseleave", () => {
                tooltip.classList.remove("show");
            });

        /* ── Click → open sidebar ── */
        node.on("click", (event, d) => {
            event.stopPropagation();
            const capsHtml = d.capabilities.length
                ? d.capabilities.map(c => `<span class="badge bg-primary bg-opacity-50 me-1 mb-1">${c}</span>`).join("")
                : "<p class='text-muted small'>No capabilities listed.</p>";

            sidebarContent.innerHTML = `
                <div class="text-center mb-4 mt-3">
                    <div class="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                         style="width:70px;height:70px;background:${ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown}30;border:2px solid ${ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown}">
                        <i class="bi bi-person-fill" style="font-size:2rem;color:${ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown}"></i>
                    </div>
                    <h5>${d.name}</h5>
                    <span class="badge" style="background:${ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown}">${d.archetype}</span>
                </div>
                <div class="mb-3">
                    <div class="text-muted small text-uppercase mb-1">Department</div>
                    <div>${d.department}</div>
                </div>
                <div class="mb-3">
                    <div class="text-muted small text-uppercase mb-1">Capabilities (${d.capability_count})</div>
                    <div class="d-flex flex-wrap gap-1">${capsHtml}</div>
                </div>
                <div class="mb-3">
                    <div class="text-muted small text-uppercase mb-1">Collaborations</div>
                    <div class="fs-4 fw-bold" style="color:${ARCHETYPE_COLORS[d.archetype] || ARCHETYPE_COLORS.Unknown}">${d.collab_count}</div>
                </div>
                <a href="/profile/${d.id}" class="btn btn-outline-info btn-sm w-100 mt-2">
                    <i class="bi bi-person-lines-fill me-1"></i>View Full Profile
                </a>
            `;
            sidebar.classList.add("open");
        });

        /* ── Close sidebar ── */
        document.getElementById("closeSidebar").addEventListener("click", () => {
            sidebar.classList.remove("open");
        });
        svg.on("click", () => sidebar.classList.remove("open"));

        /* ── Tick ── */
        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node.attr("transform", d => `translate(${d.x},${d.y})`);
        });

        /* ── Drag handlers ── */
        function dragStarted(event, d) {
            if (!event.active) simulation.alphaTarget(.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        function dragEnded(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

        /* ────────────────────────────────────────
           Search & filter
           ──────────────────────────────────────── */
        function applyFilters() {
            const searchTerm = searchInput.value.toLowerCase();
            const dept = filterDept.value;
            const arch = filterArch.value;

            node.each(function (d) {
                const g = d3.select(this);
                const matchSearch = !searchTerm || d.name.toLowerCase().includes(searchTerm);
                const matchDept = !dept || d.department === dept;
                const matchArch = !arch || d.archetype === arch;
                const visible = matchSearch && matchDept && matchArch;

                g.transition().duration(300)
                    .attr("opacity", visible ? 1 : .08);

                // Highlight searched node
                if (searchTerm && d.name.toLowerCase().includes(searchTerm)) {
                    g.select("circle:nth-child(1)")
                        .transition().duration(300)
                        .attr("stroke-opacity", 1)
                        .attr("stroke-width", 4);
                } else {
                    g.select("circle:nth-child(1)")
                        .transition().duration(300)
                        .attr("stroke-opacity", .3)
                        .attr("stroke-width", 2);
                }
            });

            link.transition().duration(300)
                .attr("stroke-opacity", .25);
        }

        searchInput.addEventListener("input", applyFilters);
        filterDept.addEventListener("change", applyFilters);
        filterArch.addEventListener("change", applyFilters);

        /* ── Handle window resize ── */
        window.addEventListener("resize", () => {
            width = wrapper.clientWidth;
            height = wrapper.clientHeight;
            simulation.force("center", d3.forceCenter(width / 2, height / 2));
            simulation.alpha(.3).restart();
        });
    }
})();

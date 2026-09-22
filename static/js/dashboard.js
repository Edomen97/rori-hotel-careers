/* ================================================================
   RORI HOTEL HAWASSA — HR ANALYTICS DASHBOARD
   Chart.js initialization
================================================================ */

(function () {
    'use strict';

    // --------------------------------------------------------
    // COLOR PALETTE
    // --------------------------------------------------------
    const COLORS = {
        navy:       '#0B132B',
        navyMid:    '#111C38',
        navyLight:  '#17264A',
        navyDeep:   '#0F1A33',
        gold:       '#C5A059',
        goldBright: '#D4AF37',
        goldLight:  '#E0C078',
        text:       '#FFFFFF',
        textMuted:  '#94A3B8',
        border:     'rgba(197, 160, 89, 0.2)',
        grid:       'rgba(255, 255, 255, 0.06)',
    };

    // Chart series palette
    const PALETTE = [
        '#C5A059', // gold
        '#3B82F6', // blue
        '#22C55E', // green
        '#EC4899', // pink
        '#8B5CF6', // purple
        '#06B6D4', // cyan
        '#F59E0B', // amber
        '#EF4444', // red
        '#14B8A6', // teal
        '#F97316', // orange
        '#A3E635', // lime
        '#E879F9', // fuchsia
    ];

    // --------------------------------------------------------
    // LOAD DATA
    // --------------------------------------------------------
    const dataEl = document.getElementById('dash-data');
    if (!dataEl) return;

    let DATA;
    try {
        DATA = JSON.parse(dataEl.textContent);
    } catch (e) {
        console.error('Failed to parse dashboard data:', e);
        return;
    }

    // --------------------------------------------------------
    // GLOBAL CHART CONFIG
    // --------------------------------------------------------
    if (window.Chart) {
        Chart.defaults.color = COLORS.textMuted;
        Chart.defaults.font.family =
            "'Plus Jakarta Sans', system-ui, sans-serif";
        Chart.defaults.font.size = 12;
        Chart.defaults.plugins.legend.labels.color = COLORS.textMuted;
        Chart.defaults.plugins.legend.labels.font = {
            size: 12,
            weight: '500',
        };
        Chart.defaults.plugins.tooltip.backgroundColor =
            'rgba(11, 19, 43, 0.95)';
        Chart.defaults.plugins.tooltip.titleColor = COLORS.gold;
        Chart.defaults.plugins.tooltip.bodyColor = COLORS.text;
        Chart.defaults.plugins.tooltip.borderColor = COLORS.gold;
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
        Chart.defaults.plugins.tooltip.titleFont = {
            weight: '700',
            size: 13,
        };
        Chart.defaults.maintainAspectRatio = false;
    }

    // --------------------------------------------------------
    // HELPERS
    // --------------------------------------------------------
    function hasData(arr) {
        return Array.isArray(arr) && arr.some((v) => v > 0);
    }

    function emptyState(canvasId, message) {
        const el = document.getElementById(canvasId);
        if (!el) return;
        const parent = el.parentElement;
        parent.innerHTML =
            '<div style="text-align:center;color:#94A3B8;padding:2rem;">' +
            '<i class="bi bi-bar-chart" ' +
            'style="font-size:2rem;color:#C5A059;opacity:0.4;' +
            'display:block;margin-bottom:0.5rem;"></i>' +
            '<div style="font-weight:600;color:#E2E8F0;">' +
            message +
            '</div></div>';
    }

    // Common axis style
    const axis = {
        grid: {
            color: COLORS.grid,
            drawBorder: false,
        },
        ticks: {
            color: COLORS.textMuted,
        },
    };

    // ========================================================
    // 1. TIMELINE (Line Chart)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartTimeline');
        if (!canvas) return;

        if (!DATA.timeline || !DATA.timeline.labels.length) {
            emptyState('chartTimeline', 'No application data yet');
            return;
        }

        new Chart(canvas, {
            type: 'line',
            data: {
                labels: DATA.timeline.labels,
                datasets: [
                    {
                        label: 'Applications',
                        data: DATA.timeline.values,
                        borderColor: COLORS.gold,
                        backgroundColor: function (context) {
                            const chart = context.chart;
                            const { ctx, chartArea } = chart;
                            if (!chartArea) return 'rgba(197, 160, 89, 0.1)';
                            const gradient = ctx.createLinearGradient(
                                0,
                                chartArea.top,
                                0,
                                chartArea.bottom
                            );
                            gradient.addColorStop(
                                0,
                                'rgba(197, 160, 89, 0.4)'
                            );
                            gradient.addColorStop(
                                1,
                                'rgba(197, 160, 89, 0)'
                            );
                            return gradient;
                        },
                        borderWidth: 2,
                        fill: true,
                        tension: 0.35,
                        pointBackgroundColor: COLORS.goldBright,
                        pointBorderColor: COLORS.navyMid,
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointHoverBackgroundColor: COLORS.goldLight,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: axis,
                    y: {
                        ...axis,
                        beginAtZero: true,
                        ticks: {
                            ...axis.ticks,
                            precision: 0,
                        },
                    },
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
            },
        });
    })();

    // ========================================================
    // 2. STATUS DISTRIBUTION (Doughnut)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartStatus');
        if (!canvas) return;

        if (!hasData(DATA.status.values)) {
            emptyState('chartStatus', 'No status data yet');
            return;
        }

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: DATA.status.labels,
                datasets: [
                    {
                        data: DATA.status.values,
                        backgroundColor: [
                            '#3B82F6',
                            '#F59E0B',
                            '#06B6D4',
                            '#EC4899',
                            '#C5A059',
                            '#22C55E',
                            '#EF4444',
                        ],
                        borderColor: COLORS.navyMid,
                        borderWidth: 3,
                        hoverOffset: 8,
                    },
                ],
            },
            options: {
                responsive: true,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 12,
                            boxWidth: 12,
                            boxHeight: 12,
                            usePointStyle: true,
                            pointStyle: 'circle',
                        },
                    },
                },
            },
        });
    })();

    // ========================================================
    // 3. APPLICATIONS BY DEPARTMENT (Horizontal Bar)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartDept');
        if (!canvas) return;

        if (!hasData(DATA.dept.values)) {
            emptyState('chartDept', 'No department data yet');
            return;
        }

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: DATA.dept.labels,
                datasets: [
                    {
                        label: 'Applications',
                        data: DATA.dept.values,
                        backgroundColor: DATA.dept.values.map(
                            (_, i) => PALETTE[i % PALETTE.length]
                        ),
                        borderRadius: 6,
                        borderSkipped: false,
                        barThickness: 18,
                    },
                ],
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ...axis,
                        beginAtZero: true,
                        ticks: {
                            ...axis.ticks,
                            precision: 0,
                        },
                    },
                    y: {
                        ...axis,
                        grid: { display: false },
                    },
                },
            },
        });
    })();

    // ========================================================
    // 4. APPLICATIONS BY EDUCATION (Bar)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartEdu');
        if (!canvas) return;

        if (!hasData(DATA.edu.values)) {
            emptyState('chartEdu', 'No education data yet');
            return;
        }

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: DATA.edu.labels,
                datasets: [
                    {
                        label: 'Applications',
                        data: DATA.edu.values,
                        backgroundColor: DATA.edu.values.map(
                            (_, i) => PALETTE[(i + 2) % PALETTE.length]
                        ),
                        borderRadius: 8,
                        borderSkipped: false,
                        barThickness: 30,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ...axis,
                        grid: { display: false },
                    },
                    y: {
                        ...axis,
                        beginAtZero: true,
                        ticks: {
                            ...axis.ticks,
                            precision: 0,
                        },
                    },
                },
            },
        });
    })();

    // ========================================================
    // 5. APPLICATIONS BY JOB (Horizontal Bar)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartJobs');
        if (!canvas) return;

        if (!hasData(DATA.jobs.values)) {
            emptyState('chartJobs', 'No job position data yet');
            return;
        }

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: DATA.jobs.labels,
                datasets: [
                    {
                        label: 'Applications',
                        data: DATA.jobs.values,
                        backgroundColor: DATA.jobs.values.map(
                            (_, i) => PALETTE[i % PALETTE.length]
                        ),
                        borderRadius: 6,
                        borderSkipped: false,
                        barThickness: 22,
                    },
                ],
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ...axis,
                        beginAtZero: true,
                        ticks: {
                            ...axis.ticks,
                            precision: 0,
                        },
                    },
                    y: {
                        ...axis,
                        grid: { display: false },
                    },
                },
            },
        });
    })();

    // ========================================================
    // 6. INTERVIEW ANALYTICS (Doughnut)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartInterviews');
        if (!canvas) return;

        if (!hasData(DATA.interviews.values)) {
            emptyState('chartInterviews', 'No interviews scheduled');
            return;
        }

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: DATA.interviews.labels,
                datasets: [
                    {
                        data: DATA.interviews.values,
                        backgroundColor: [
                            '#C5A059',
                            '#22C55E',
                            '#EF4444',
                            '#F59E0B',
                            '#3B82F6',
                        ],
                        borderColor: COLORS.navyMid,
                        borderWidth: 3,
                        hoverOffset: 8,
                    },
                ],
            },
            options: {
                responsive: true,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 12,
                            boxWidth: 12,
                            boxHeight: 12,
                            usePointStyle: true,
                            pointStyle: 'circle',
                        },
                    },
                },
            },
        });
    })();

    // ========================================================
    // 7. TALENT POOL — EDUCATION (Pie)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartTalent');
        if (!canvas) return;

        if (!hasData(DATA.talent.values)) {
            emptyState('chartTalent', 'Talent pool is empty');
            return;
        }

        new Chart(canvas, {
            type: 'pie',
            data: {
                labels: DATA.talent.labels,
                datasets: [
                    {
                        data: DATA.talent.values,
                        backgroundColor: DATA.talent.labels.map(
                            (_, i) => PALETTE[i % PALETTE.length]
                        ),
                        borderColor: COLORS.navyMid,
                        borderWidth: 3,
                        hoverOffset: 8,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 12,
                            boxWidth: 12,
                            boxHeight: 12,
                            usePointStyle: true,
                            pointStyle: 'circle',
                        },
                    },
                },
            },
        });
    })();

    // ========================================================
    // 8. TALENT POOL — LOCATIONS (Horizontal Bar)
    // ========================================================
    (function () {
        const canvas = document.getElementById('chartTalentLoc');
        if (!canvas) return;

        if (!hasData(DATA.talentLoc.values)) {
            emptyState('chartTalentLoc', 'No location data yet');
            return;
        }

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: DATA.talentLoc.labels,
                datasets: [
                    {
                        label: 'Candidates',
                        data: DATA.talentLoc.values,
                        backgroundColor: DATA.talentLoc.values.map(
                            (_, i) => PALETTE[(i + 4) % PALETTE.length]
                        ),
                        borderRadius: 6,
                        borderSkipped: false,
                        barThickness: 22,
                    },
                ],
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: {
                        ...axis,
                        beginAtZero: true,
                        ticks: {
                            ...axis.ticks,
                            precision: 0,
                        },
                    },
                    y: {
                        ...axis,
                        grid: { display: false },
                    },
                },
            },
        });
    })();

})();
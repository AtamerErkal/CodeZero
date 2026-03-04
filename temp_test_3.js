
    tailwind.config = {
        darkMode: 'class',
        theme: {
            extend: {
                colors: {
                    navy: { 800: '#1E2A3B', 900: '#0F172A', 950: '#0B1120' },
                    clinical: {
                        red: '#EF4444', redBg: '#FEF2F2',
                        amber: '#F59E0B', amberBg: '#FFFBEB',
                        emerald: '#10B981', emeraldBg: '#ECFDF5'
                    }
                },
                fontFamily: {
                    sans: ['DM Sans', 'sans-serif'],
                    display: ['Syne', 'sans-serif'],
                    mono: ['JetBrains Mono', 'monospace']
                },
                animation: {
                    'edge-glow': 'edgeGlow 2s infinite',
                    'pulse-ring': 'pulse-ring 1.5s ease-out infinite'
                },
                keyframes: {
                    edgeGlow: {
                        '0%, 100%': { boxShadow: 'inset 0 0 0 #EF4444' },
                        '50%': { boxShadow: 'inset 0 0 40px #EF4444' }
                    },
                    'pulse-ring': {
                        '0%': { transform: 'scale(1)', opacity: '0.8' },
                        '100%': { transform: 'scale(2.5)', opacity: '0' }
                    }
                }
            }
        }
    }

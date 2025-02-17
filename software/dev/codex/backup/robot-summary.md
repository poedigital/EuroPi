Codex Project Overview
modular eurorack scripting, firmware, and desktop integration
1. project summary
the codex project is an advanced eurorack modular synthesis ecosystem, integrating a custom scripting engine, a bytecode processing unit, and a waveform generation engine. it spans across euroPi-based eurorack modules, a desktop application for editing and maintaining consistency, and a data storage system for equations and presets. codex is built to enable real-time control, state management, and hardware integration, acting as both a sequencer and a computational engine for modular synthesis.

core components:
codex.py – the heart of the project, a computational and scripting engine that will integrate waveform sequencing, bytecode processing, and real-time control for eurorack modules.
byte-forge – a bytecode processing unit that enables equation storage and recall, acting as a code execution layer for the codex system.
wave engine – an advanced waveform generation system, planned for state 3 integration, providing enhanced audio and cv synthesis capabilities.
desktop application – a centralized software interface to edit, maintain, and ensure consistency across codex scripts and bytecode equations.
euroPi firmware – a custom firmware that acts as the reader application for executing codex scripts within the eurorack ecosystem.
state storage and equation management – a structured dictionary system to store equations, settings, and presets across the ecosystem.
2. project index
hardware and firmware references
dev-index.md
a technical reference for hardware compatibility and firmware integration
lists firmware specifications, supported hardware, and interconnectivity details
used as a hardware blueprint for codex-based eurorack expansion
scripting and engine roadmap
EuroPi_Codex_Roadmap.md
documents the current implementation and future phases of codex.py
describes the initial concept, design rationale, and planned expansions
acts as a development guide for integrating codex into the eurorack module
core processing units
codex_0.5.py (codex engine – current state)

the main computational engine for the eurorack integration
manages scripting, data processing, and eurorack control
to be integrated with byte-forge and the wave engine in later states
byte-forge_1.8.py (bytecode execution layer)

processes and stores equations for later execution in codex.py
enables script execution, modular signal computation, and real-time processing
designed to function as a backend processor for eurorack scripting
waveform computation and visualization
test-waveform.py (wave engine – state 3)

advanced waveform generator planned for integration into codex.py
provides real-time audio/cv synthesis capabilities
allows procedural waveform generation within the modular system
test-matrix.py (state 2 integration of codex.py)

handles matrix-based computation for cv sequencing, modular signal routing
prepares a multi-dimensional state system for the next codex version
state management and storage
saved_state_Codex.txt
a dictionary file storing equations and scripts
used by byte-forge for equation recall and processing
display and visualization tools
oled_emulator.py
an emulation tool for previewing unsupported characters in the byte-forge engine
ensures display compatibility before deploying scripts to hardware
3. development roadmap
phase 1: core engine development (current)
refine codex.py to execute stored scripts and respond to real-time control
integrate byte-forge for equation storage and recall
test core cv sequencing and signal processing capabilities
phase 2: state-based expansion
integrate test-matrix.py to handle multi-dimensional sequencing
improve state storage and recall efficiency
optimize computational performance in euroPi
phase 3: waveform synthesis integration
implement test-waveform.py into codex.py
introduce procedural waveform generation within eurorack
enable real-time waveform manipulation via modular control
phase 4: final integration and desktop control
finalize desktop application for managing and maintaining scripts
optimize display handling and visualization using oled_emulator.py
refine firmware interaction and ensure seamless eurorack execution
4. project purpose & future direction
the codex project aims to bridge modular synthesis with programmable scripting, creating a fully customizable eurorack control environment. through structured bytecode execution, real-time waveform computation, and a modular scripting engine, it allows for precise sequencing, automation, and algorithmic composition. future iterations will refine cv control, signal processing, and eurorack modular interaction, making codex a powerful tool for generative and structured synthesis.
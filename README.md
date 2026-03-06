# 🏗️ Twin Crane Scheduling Simulation
**A Discrete-Event Simulation Testbed for Multi-Agent Spatial Routing**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Pygame](https://img.shields.io/badge/Pygame-UI_Engine-green)
![Salabim](https://img.shields.io/badge/Salabim-DES_Backend-orange)
![License](https://img.shields.io/badge/License-MIT-purple)



## 📖 Overview
In heavy industrial environments (such as steel mills, automotive stamping plants, and container terminals), overhead cranes frequently share the same physical runway rails. This creates a highly complex scheduling challenge known as the **Vehicle Routing Problem with Spatial Constraints (VRPSC).**

Because the cranes cannot pass each other, the system is highly susceptible to spatial deadlocks. This repository provides a robust **Discrete-Event Simulation (DES)** environment to test, visualize, and debug rule-based scheduling approaches for twin-crane systems. 

### 🎥 Simulation Demo
![Demo](assets/Twin_Crane.gif)
<!-- *(Placeholder: Drop your `demo.gif` in the root folder and uncomment the line below)* -->
<!-- --- -->

## ⚙️ The Core Challenge: Spatial Deadlocks & Starvation
When multiple agents operate on a shared 1D plane, they are strictly bound by the non-crossing constraint. At any given time step $t$, the Left Crane ($C_1$) and Right Crane ($C_2$) must satisfy:

$$Position_{C_1}(t) < Position_{C_2}(t) \quad \forall t$$

Standard greedy scheduling algorithms typically result in two failure states:
1. **Physical Deadlock:** Both cranes accept overlapping jobs, meet in the middle, and freeze indefinitely.
2. **Job Starvation:** The dispatcher becomes overly conservative, assigning massive "safety zones" to one crane while the other sits idle, causing the facility's job queue to bottleneck.

---

## 🧠 The Open-Source Solution: Strict Spatial JIT Dispatching
This public codebase implements a **Just-In-Time (JIT) Rule-Based Dispatcher**. It is designed to act as a highly visual, deadlock-free baseline for industrial routing.

### Key Features
* **Just-In-Time Assignment:** Cranes are forbidden from queueing jobs. They are assigned tasks at the exact millisecond they become idle, minimizing the tracks they "reserve" and leaving the rest of the facility open.
* **Strict Spatial Future-Pathing:** Before a job is dispatched, the algorithm projects the entire required spatial zone of the proposed job. If it intersects with the active zone of the other crane, the job is deferred.
* **Dynamic Escape Routing:** If an idle crane is blocking the path of an active crane, the active crane dynamically calculates a safe "escape track" and dispatches a dummy relocate command, pushing the idle crane out of the way.

---

## 🔬 Advanced Optimization (Proprietary)


While the rule-based dispatcher provided in this repository successfully prevents physical deadlocks, rule-based systems are inherently sub-optimal during heavy facility loads. 

**Note:** We have successfully formulated and solved this exact twin-crane system as a **Mixed Integer Linear Programming (MILP)** optimization problem to minimize total empty travel distance (thereby minimizing energy consumption and cycle times):

$$\min \sum_{c \in C} \sum_{i,j \in J} d(D_i, P_j) \cdot X_{c,i,j}$$

*(Where $d$ is distance, $D_i$ is dropoff of job $i$, $P_j$ is pickup of job $j$, and $X$ is a binary routing variable).*

Due to confidentiality and proprietary constraints, the MILP solver backend (using Gurobi/PuLP) is **not included in this repository**. However, the provided Pygame/Salabim simulation remains a highly valuable testbed for observing the complexities of spatial routing, testing custom heuristic algorithms, and validating baseline efficiency.

---

## 🛠️ Architecture & Tech Stack
This project completely separates the heavy lifting of the simulation logic from the visualization engine.

* **Backend (Simulation Engine): [Salabim](https://www.salabim.org/)**
  Handles the DES queuing, yielding mechanics, temporal spacing, and event logging.
* **Frontend (Rendering Engine): [Pygame](https://www.pygame.org/)**
  Replaces standard laggy UI libraries with a hardware-accelerated, 60 FPS industrial dashboard.

---

## 🚀 Installation & Usage

### Prerequisites
Ensure you have Python 3.8+ installed.

### Setup
1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/twin-crane-simulation.git](https://github.com/YOUR_USERNAME/twin-crane-simulation.git)
   cd twin-crane-simulation
#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
## Map database upgrade (iteration 5)
- Backend: new /app/backend/geo.py router — /api/geo/search (Photon autocomplete + Nominatim fallback + local DB + India Post PIN), /api/geo/place/{loc_id} (enrich), /api/geo/reverse (?exact=true keeps pin), /api/geo/pincode/{pin}, /api/geo/route (OSRM + FOSSGIS mirror, alternatives, geometry, toll estimate), /api/geo/nearby (Overpass mirrors -> Photon fallback), /api/geo/status, /api/admin/geo/sync, /api/admin/geo/report. Legacy /api/locations/search, /locations/osm, /locations/reverse, /route/estimate kept.
- Trips store route_line (GeoJSON, 2dsphere), route_via, toll_estimate; GET /api/trips/{id} returns `route` [[lat,lng]]; /api/trips/search matches along-route (match.type along_route) in correct direction.
- Frontend: OsmMap (Leaflet/OSM in WebView / iframe), MapPicker, new LocationSearchModal (unified autocomplete, map preview, pick on map, last sync date), offer route map + alternatives + nearby pickup chips + auto toll, trip route map, RideCard along-route badge, admin Map database card, add-place OSM pin map.

## Iteration 17 — Unified Local Driver (Rent a Driver + Book a Driver), destination-taluk matching
- Backend (server.py): pro_drivers gains services [rent|book], service_areas/service_taluk_codes, cities_covered, accepts_outstation, accepts_outside_area, availability_status (available|busy|offline, synced to legacy `available`), blocked_dates, vehicles[] (Book only). Legacy profiles default to services=["rent"].
- New: PUT /api/pro/settings, PUT /api/pro/vehicles, GET /api/pro/dashboard, GET/POST /api/hire/favourites[/{driver_id}], POST /api/hire/bookings/{bid}/arriving, GET /api/admin/hire-bookings?service=, GET /api/admin/hire-reports, GET /api/admin/pro-drivers?service=.
- Changed: GET /api/hire/local-drivers and POST /api/hire/requests: subdistrict_code = DESTINATION taluk; service + service_type (rent: hourly/half_day/full_day/multi_day/outstation; book: one_way/round_trip/multi_day/outstation), days, vehicle_type, passengers, pickup_subdistrict_code, driver_id (direct request). Decline-all -> request status declined + customer notified.
- Backend test: backend/tests/test_iter17_unified_local_driver.py — 14/14 pass.
- Frontend: app/hire/index.tsx (Rent/Book chooser + forms + results), app/hire/driver.tsx (new dashboard), app/hire/register.tsx (services, areas, vehicles), app/hire/requests.tsx, app/hire/[id].tsx (vehicle, arriving, favourite, report), admin/dashboard.tsx (Local drivers filters + Driver hire bookings + Driver reports tabs), src/components/LocalDriverParts.tsx.

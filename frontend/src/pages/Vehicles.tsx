import { useEffect, useState } from "react";
import { Search, Car, Truck, Bus, Bike, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { useSocket } from "@/hooks/useSocket";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { formatTime } from "@/lib/utils";

export function Vehicles() {
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedVehicle, setSelectedVehicle] = useState<any | null>(null);
  const [vehicleEvents, setVehicleEvents] = useState<any[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const { onEvent } = useSocket();

  useEffect(() => {
    fetchVehicles();
  }, [currentPage]);

  useEffect(() => {
    const unsubscribe = onEvent((msg: any) => {
      if (msg.type === "event" && selectedVehicle) {
        fetchVehicleEvents(selectedVehicle.id);
      }
    });
    return unsubscribe;
  }, [onEvent, selectedVehicle]);

  const fetchVehicles = async () => {
    setLoading(true);
    try {
      const data = await api.listVehicles(currentPage, 20);
      setVehicles(data.items);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error("Failed to fetch vehicles:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchVehicleEvents = async (vehicleId: number) => {
    setEventsLoading(true);
    try {
      const events = await api.getVehicleEvents(vehicleId);
      setVehicleEvents(events);
    } catch (error) {
      console.error("Failed to fetch vehicle events:", error);
    } finally {
      setEventsLoading(false);
    }
  };

  const handleSelectVehicle = (vehicle: any) => {
    setSelectedVehicle(vehicle);
    fetchVehicleEvents(vehicle.id);
  };

  const filteredVehicles = vehicles.filter((v) =>
    (v.vehicle_type || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (v.color || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (v.make_model || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (v.license_plate || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getVehicleIcon = (type?: string) => {
    switch (type?.toLowerCase()) {
      case "truck": return <Truck className="h-4 w-4" />;
      case "bus": return <Bus className="h-4 w-4" />;
      case "motorcycle": return <Bike className="h-4 w-4" />;
      default: return <Car className="h-4 w-4" />;
    }
  };

  const getTypeBadge = (type?: string) => {
    switch (type?.toLowerCase()) {
      case "truck": return <Badge variant="secondary">Truck</Badge>;
      case "bus": return <Badge variant="outline">Bus</Badge>;
      case "motorcycle": return <Badge variant="default">Motorcycle</Badge>;
      default: return <Badge variant="default">Car</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Skeleton className="h-8 w-32" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[...Array(8)].map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-32 w-full rounded-lg mb-3" />
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-4 w-16" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Vehicles</h1>
          <p className="text-muted-foreground">Detected vehicles across all videos</p>
        </div>
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search vehicles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Vehicle Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {filteredVehicles.length === 0 ? (
          <div className="col-span-full text-center py-12 text-muted-foreground">
            No vehicles found
          </div>
        ) : (
          filteredVehicles.map((vehicle) => (
            <Card
              key={vehicle.id}
              className="cursor-pointer transition-shadow hover:shadow-lg"
              onClick={() => handleSelectVehicle(vehicle)}
            >
              <CardContent className="p-4">
                <div className="aspect-video relative mb-3 rounded-lg bg-muted overflow-hidden">
                  {vehicle.thumbnail_url ? (
                    <img
                      src={vehicle.thumbnail_url}
                      alt={`Vehicle ${vehicle.id}`}
                      className="object-cover w-full h-full"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      {getVehicleIcon(vehicle.vehicle_type)}
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">Vehicle #{vehicle.id}</p>
                    <p className="text-xs text-muted-foreground">
                      Video #{vehicle.video_id} · {formatTime(vehicle.first_seen)} - {formatTime(vehicle.last_seen)}
                    </p>
                  </div>
                  {getTypeBadge(vehicle.vehicle_type)}
                </div>
                <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                  {vehicle.color && (
                    <Badge variant="outline" className="gap-1">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: vehicle.color }} />
                      {vehicle.color}
                    </Badge>
                  )}
                  {vehicle.make_model && <Badge variant="outline">{vehicle.make_model}</Badge>}
                  {vehicle.license_plate && <Badge variant="outline">{vehicle.license_plate}</Badge>}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  {vehicle.event_count} event{vehicle.event_count !== 1 ? "s" : ""}
                  {vehicle.last_event_type && ` · Last: ${vehicle.last_event_type}`}
                </p>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Vehicle Detail Modal */}
      {selectedVehicle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-card w-full max-w-4xl max-h-[85vh] rounded-lg shadow-xl flex flex-col overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-3">
                <div className="aspect-square w-16 h-16 rounded-lg bg-muted flex items-center justify-center overflow-hidden">
                  {selectedVehicle.thumbnail_url ? (
                    <img src={selectedVehicle.thumbnail_url} alt="" className="object-cover w-full h-full" />
                  ) : (
                    getVehicleIcon(selectedVehicle.vehicle_type)
                  )}
                </div>
                <div>
                  <h2 className="font-semibold">Vehicle #{selectedVehicle.id}</h2>
                  <p className="text-sm text-muted-foreground">
                    Video #{selectedVehicle.video_id} · {getTypeBadge(selectedVehicle.vehicle_type)}
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setSelectedVehicle(null)}>
                <ChevronLeft className="h-5 w-5" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <div className="grid gap-4 mb-6">
                {selectedVehicle.color && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground w-24">Color:</span>
                    <Badge variant="outline" className="gap-1">
                      <span className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedVehicle.color }} />
                      {selectedVehicle.color}
                    </Badge>
                  </div>
                )}
                {selectedVehicle.make_model && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground w-24">Model:</span>
                    <Badge variant="default">{selectedVehicle.make_model}</Badge>
                  </div>
                )}
                {selectedVehicle.license_plate && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground w-24">Plate:</span>
                    <Badge variant="secondary">{selectedVehicle.license_plate}</Badge>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground w-24">Time:</span>
                  <span className="text-sm">
                    {formatTime(selectedVehicle.first_seen)} - {formatTime(selectedVehicle.last_seen)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground w-24">Events:</span>
                  <span className="text-sm">{selectedVehicle.event_count}</span>
                </div>
              </div>

              <div className="border-t pt-4">
                <h3 className="font-medium mb-3">Events ({vehicleEvents.length})</h3>
                {eventsLoading ? (
                  <div className="space-y-3">
                    {[...Array(3)].map((_, i) => (
                      <Skeleton key={i} className="h-16 w-full rounded" />
                    ))}
                  </div>
                ) : vehicleEvents.length === 0 ? (
                  <p className="text-muted-foreground text-center py-4">No events for this vehicle</p>
                ) : (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {vehicleEvents.map((event) => (
                      <Card key={event.id} className="p-3">
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-16 h-16 rounded bg-muted flex items-center justify-center overflow-hidden">
                            {event.thumbnail_url ? (
                              <img src={event.thumbnail_url} alt="" className="object-cover w-full h-full" />
                            ) : (
                              getVehicleIcon(event.objects?.[0])
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{event.event_type}</Badge>
                              <span className="text-xs text-muted-foreground">
                                {formatTime(event.timestamp)}
                              </span>
                            </div>
                            <p className="text-sm mt-1">{event.description}</p>
                            {event.objects && event.objects.length > 0 && (
                              <div className="flex gap-1 mt-1 flex-wrap">
                                {event.objects.map((obj: string) => (
                                  <Badge key={obj} variant="secondary" className="text-xs">
                                    {obj}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
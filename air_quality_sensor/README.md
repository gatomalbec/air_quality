┌──────────── Sensor Threads (one per driver) ─────────────┐
│  PMThread             CO₂Thread              VOCThread   │
│       │                    │                     │       │
│       └───── SensorReading[T] instances ─────────┘       │
└───────────────────────────┬──────────────────────────────┘
                            ▼
                 ┌────────────────────────┐
                 │  Bounded Queue (FIFO)  │  ◄─ OverflowPolicy*
                 └────────────────────────┘
                            │
                            ▼
                 ┌────────────────────────┐        uses
                 │      DeliveryLoop      │ ─────► BackoffPolicy**
                 │  (pure orchestrator)   │
                 └─────────┬──────────────┘
                           │  calls OutboundPort.send()
                           ▼
          ┌───────────────────────────────────────────┐
          │            OutboundPortImpl               │
          │      “BufferedPusher” composite           │
          └─────────┬────────────────────┬────────────┘
                    │                    │
                    │ (durability first) │ (network I/O)
                    ▼                    ▼
          ┌─────────────────┐   ┌────────────────────┐
          │  BufferWriter   │   │    MessagePusher   │
          │  (SQLite ring)  │   │   (MQTTPusher)     │
          └────────┬────────┘   └────────┬──────────┘
                   │                     │
                   └─ mark_sent(id) ◄────┘  on publish-ACK

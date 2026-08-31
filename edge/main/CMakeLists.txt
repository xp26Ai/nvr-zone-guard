idf_component_register(SRCS "app_main.cpp"
                            "camera.cpp"
                            "wifi.cpp"
                            "telegram.cpp"
                            "zone.cpp"
                            "detect.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES esp32-camera esp-dl)

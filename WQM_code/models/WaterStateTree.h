#pragma once
#include <stdarg.h>   // AVR-compatible
namespace Eloquent {
    namespace ML {
        namespace Port {
            class WaterStateTree {
                public:
                    /**
                    * Predict class for features vector
                    */
                    int predict(float *x) {
                        if (x[2] <= 1.5694687366485596) {
                            if (x[1] <= 1.4125218391418457) {
                                if (x[2] <= 1.3498284816741943) {
                                    if (x[2] <= 1.2393893599510193) {
                                        if (x[4] <= 3.0160000324249268) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[4] <= -0.23600000143051147) {
                                            return 0;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }

                                else {
                                    if (x[0] <= -0.1834999993443489) {
                                        if (x[0] <= -0.6762999892234802) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[4] <= 0.271000012755394) {
                                            return 0;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }
                            }

                            else {
                                return 2;
                            }
                        }

                        else {
                            if (x[1] <= 1.1847092509269714) {
                                if (x[4] <= -0.4389999955892563) {
                                    if (x[1] <= 1.0519623160362244) {
                                        if (x[3] <= -11.880000114440918) {
                                            return 2;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[3] <= -8.329999923706055) {
                                            return 2;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }

                                else {
                                    if (x[4] <= 1.2559999823570251) {
                                        if (x[0] <= -0.023099999874830246) {
                                            return 1;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }

                                    else {
                                        if (x[2] <= 2.0628544092178345) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }
                                }
                            }

                            else {
                                if (x[1] <= 1.3287010192871094) {
                                    if (x[4] <= -1.487500011920929) {
                                        return 2;
                                    }

                                    else {
                                        if (x[4] <= 0.01000000024214387) {
                                            return 0;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }
                                }

                                else {
                                    if (x[0] <= 0.002699999953620136) {
                                        return 2;
                                    }

                                    else {
                                        if (x[0] <= 0.006500000134110451) {
                                            return 0;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }
                                }
                            }
                        }
                    }

                    /**
                    * Predict readable class name
                    */
                    const char* predictLabel(float *x) {
                        return idxToLabel(predict(x));
                    }

                    /**
                    * Convert class idx to readable name
                    */
                    const char* idxToLabel(uint8_t classIdx) {
                        switch (classIdx) {
                            case 0:
                            return "NORMAL";
                            case 1:
                            return "NATURAL";
                            case 2:
                            return "ALERT";
                            default:
                            return "Houston we have a problem";
                        }
                    }

                protected:
                };
            }
        }
    }
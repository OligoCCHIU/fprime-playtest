// ======================================================================
// \title  MathSenderTester.cpp
// \author cindy
// \brief  cpp file for MathSender component test harness implementation class
// ======================================================================

#include "MathSenderTester.hpp"

namespace MathModule {

  // ----------------------------------------------------------------------
  // Construction and destruction
  // ----------------------------------------------------------------------

  MathSenderTester ::
    MathSenderTester() :
      MathSenderGTestBase("MathSenderTester", MathSenderTester::MAX_HISTORY_SIZE),
      component("MathSender")
  {
    this->initComponents();
    this->connectPorts();
  }

  MathSenderTester ::
    ~MathSenderTester()
  {

  }

  // ----------------------------------------------------------------------
  // Tests
  // ----------------------------------------------------------------------

  void MathSenderTester ::
    toDo()
  {
    // TODO
  }

}

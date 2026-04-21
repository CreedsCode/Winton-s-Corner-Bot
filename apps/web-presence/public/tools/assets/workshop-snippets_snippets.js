const snippets = [
  {
    id: 1,
    title: "Skip team assembly phase",
    description: "Skips the hero selection time",
    code: `rule("Skip team assembly phase")
{
	event
	{
		Ongoing - Global;
	}

	conditions
	{
		Is Assembling Heroes == True;
	}

	actions
	{
		Set Match Time(0);
	}
}`
  },
  {
    id: 2,
    title: "Skip setup phase",
    description: "Skips the setup time",
    code: `rule("Skip setup phase")
{
	event
	{
		Ongoing - Global;
	}

	conditions
	{
		Is In Setup == True;
	}

	actions
	{
		Set Match Time(0);
	}
}`
  },
  {
    id: 3,
    title: "Ultimate ability is free",
    description: "Automatically ready up the ultimate ability when players try to use it",
    code: `rule("Ultimate ability is free")
{
	event
	{
		Ongoing - Each Player;
		All;
		All;
	}

	conditions
	{
		Is Button Held(Event Player, Button(Ultimate)) == True;
	}

	actions
	{
		Set Ultimate Charge(Event Player, 100);
	}
}`
  },{
	id: 4,
	title: "Teleport self to point",
	description: "Teleport yourself to point using interact + crouch + primary fire",
	code: `rule("Teleport self to objective")
{
	event
	{
		Ongoing - Each Player;
		All;
		All;
	}

	conditions
	{
		Is Button Held(Event Player, Button(Interact)) == True;
		Is Button Held(Event Player, Button(Crouch)) == True;
		Is Button Held(Event Player, Button(Primary Fire)) == True;
	}

	actions
	{
		Teleport(Event Player, Objective Position(0));
	}
}`
  }
];
